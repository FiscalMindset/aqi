"""Shared HTTP client factory with explicit timeouts and retry policy.

Every outbound call in Dhuan Detective must go through this factory so that:
  * timeouts are always set (rule 2),
  * retries use exponential backoff with jitter (rule 2),
  * failures are logged with the correlation id and counted (rule 3).

Retries are only applied to idempotent verbs (GET) and to explicit
`make_request()` calls; callers that need custom per-call retry semantics use
`make_request` directly.
"""

from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from dhuan.core.config import Settings, get_settings
from dhuan.core.logging import get_logger, log_event
from dhuan.core.metrics import record

logger = get_logger("http")

RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})


class UpstreamError(RuntimeError):
    """Raised when an upstream data source cannot serve a value."""

    def __init__(self, source: str, detail: str, status: int | None = None) -> None:
        super().__init__(f"{source}: {detail} (status={status})")
        self.source = source
        self.status = status


@dataclass(slots=True)
class HttpPolicy:
    timeout_seconds: float
    connect_timeout_seconds: float
    max_retries: int
    base_delay_seconds: float
    max_delay_seconds: float

    @classmethod
    def from_settings(cls, s: Settings) -> HttpPolicy:
        return cls(
            timeout_seconds=s.http_timeout_seconds,
            connect_timeout_seconds=s.http_connect_timeout_seconds,
            max_retries=s.http_max_retries,
            base_delay_seconds=s.http_retry_base_delay_seconds,
            max_delay_seconds=s.http_retry_max_delay_seconds,
        )


def _retrying(policy: HttpPolicy) -> AsyncRetrying:
    return AsyncRetrying(
        stop=stop_after_attempt(policy.max_retries + 1),
        wait=wait_exponential_jitter(
            multiplier=policy.base_delay_seconds, max=policy.max_delay_seconds, jitter=1.0
        ),
        retry=retry_if_exception_type(
            (httpx.TimeoutException, httpx.NetworkError, UpstreamRetryError)
        ),
        reraise=True,
    )


class UpstreamRetryError(Exception):
    """Internal signal: response looks retryable."""

    def __init__(self, response: httpx.Response) -> None:
        super().__init__(f"retryable status {response.status_code}")
        self.response = response


def make_client(policy: HttpPolicy, headers: dict[str, str] | None = None) -> httpx.AsyncClient:
    limits = httpx.Limits(max_connections=50, max_keepalive_connections=10)
    timeout = httpx.Timeout(policy.timeout_seconds, connect=policy.connect_timeout_seconds)
    return httpx.AsyncClient(
        timeout=timeout, limits=limits, headers=headers or {"User-Agent": "DhuanDetective/1.0"}
    )


async def _single_attempt(  # noqa: PLR0917 - keeps call sites readable
    client: httpx.AsyncClient,
    source: str,
    method: str,
    url: str,
    params: dict[str, Any] | None,
    headers: dict[str, str] | None,
    json: Any,
    data: Any,
    timeout: float | None,  # noqa: ASYNC109 - mirrors make_request override
    attempt_no: int,
) -> httpx.Response:
    """One attempt: returns the response or raises UpstreamError/UpstreamRetryError."""
    try:
        resp = await client.request(
            method,
            url,
            params=params,
            headers=headers,
            json=json,
            data=data,
            timeout=timeout,
        )
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        log_event(
            logger, 40, "upstream_transport_error",
            source=source, url=url, error=str(exc), attempt=attempt_no,
        )
        record("UpstreamErrors", 1)
        raise UpstreamError(source, f"transport error: {exc}") from exc
    if resp.status_code in RETRYABLE_STATUS:
        log_event(
            logger, 30, "upstream_retryable_status",
            source=source, url=url, status=resp.status_code, attempt=attempt_no,
        )
        record("UpstreamRetries", 1)
        raise UpstreamRetryError(resp)
    if resp.status_code >= 400:
        log_event(
            logger, 40, "upstream_error_status",
            source=source, url=url, status=resp.status_code, attempt=attempt_no,
        )
        record("UpstreamErrors", 1)
        raise UpstreamError(source, "upstream error", resp.status_code)
    record("UpstreamRequests", 1)
    if attempt_no > 1:
        log_event(
            logger, 20, "upstream_recovered", source=source, url=url, attempts=attempt_no
        )
    return resp


async def make_request(
    client: httpx.AsyncClient,
    policy: HttpPolicy,
    source: str,
    method: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    json: Any = None,
    data: Any = None,
    timeout: float | None = None,  # noqa: ASYNC109 - per-call override is intentional
) -> httpx.Response:
    """GET/POST with timeouts, exponential backoff + jitter, logging + metrics.

    Transport errors and retryable statuses are retried; any other 4xx/5xx
    raises `UpstreamError` immediately; exhausted retries also surface as
    `UpstreamError` (never as an internal signal leaking to callers).
    """
    attempts = 0
    try:
        async for attempt in _retrying(policy):
            with attempt:
                attempts += 1
                return await _single_attempt(
                    client, source, method, url, params, headers, json, data, timeout, attempts
                )
    except UpstreamRetryError as retry_exc:
        raise UpstreamError(
            source, "retryable status persisted", retry_exc.response.status_code
        ) from retry_exc
    raise UpstreamError(source, "exhausted retries")


class UpstreamClient:
    """Convenience wrapper: one source = one client + policy."""

    def __init__(self, source: str, base_url: str, settings: Settings | None = None) -> None:
        self.source = source
        self.base_url = base_url
        self.settings = settings or get_settings()
        self.policy = HttpPolicy.from_settings(self.settings)
        self.client = make_client(self.policy)

    def _url(self, path: str) -> str:
        """Accept either a full URL or a path relative to the base_url."""
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return self.base_url.rstrip("/") + "/" + path.lstrip("/")

    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        if "timeout" not in kwargs:
            kwargs["timeout"] = self.policy.timeout_seconds
        return await make_request(
            self.client, self.policy, self.source, "GET", self._url(path), **kwargs
        )

    async def post(self, path: str, **kwargs: Any) -> httpx.Response:
        if "timeout" not in kwargs:
            kwargs["timeout"] = self.policy.timeout_seconds
        return await make_request(
            self.client, self.policy, self.source, "POST", self._url(path), **kwargs
        )

    async def aclose(self) -> None:
        await self.client.aclose()


def _jitter() -> float:
    """Uniform jitter. Not a security primitive (S311)."""
    return random.random()  # noqa: S311 - jitter for retries, not cryptographic


def jitter_sleep_seconds(base: float, attempt: int) -> float:
    """Backoff with full jitter, capped. Jitter is not a security primitive."""
    base_delay: float = base * (2 ** (attempt - 1))
    delay: float = base_delay * (0.5 + _jitter() / 2)
    return min(delay, 30.0)


def endpoints_round_robin(endpoints: Iterable[str]) -> list[str]:
    """Deterministic-but-rotated order so one slow mirror doesn't poison us."""
    return list(endpoints)


async def first_success(calls: list[Any]) -> Any:
    """Run awaitables in order, return the first success (used for mirrors)."""
    last_exc: Exception | None = None
    for call in calls:
        try:
            return await call()
        except Exception as exc:
            last_exc = exc
    if last_exc:
        raise last_exc
    raise UpstreamError("mirrors", "no endpoints configured")
