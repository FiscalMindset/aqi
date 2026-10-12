"""Optional Groq pass that rewords an already-grounded explanation.

The contract, which the tests enforce:

1. The deterministic composer has **already** produced the answer. Groq never
   generates facts.
2. Groq may only improve fluency and readability. It receives the composed text
   plus the passages it was built from.
3. The rewritten text is rejected unless it introduces **no new numbers**. We
   compare the numeric tokens in the rewrite against the original; any number
   that was not in the grounded text means the model invented a measurement, and
   we discard the rewrite and keep the original.
4. Any failure at all - no key, timeout, 429, 5xx, malformed JSON, empty reply,
   refusal, or the guard firing - returns the original text. The explanation is
   never blocked on Groq.

This is why the product does not need a working LLM to explain itself: this
module is an improvement, and its failure mode is "nothing happened".
"""

from __future__ import annotations

import re
from typing import Any

from dhuan.core.config import Settings
from dhuan.core.logging import get_logger
from dhuan.core.metrics import record

logger = get_logger("agents.groq")

# A number as it would appear in prose: 223, 11.1, 62, 2014-11-24h, 80%.
# We strip thousands separators so "1,200" and "1200" compare equal.
NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")

SYSTEM = (
    "You edit text for clarity. You are given a factual explanation and the "
    "evidence passages it was written from. Rewrite it to read more naturally "
    "for a general audience.\n\n"
    "Hard rules, in order of importance:\n"
    "1. Never introduce a number, name, place or date that is not already in "
    "the original text or the passages.\n"
    "2. Never add a claim, cause, recommendation or conclusion.\n"
    "3. Never remove a caveat, a hedge, or an uncertainty statement.\n"
    "4. Keep every measurement exactly as written.\n"
    "5. Keep the same meaning and the same order of ideas.\n"
    "6. Return only the rewritten text, no preamble, no quotes, no headings.\n\n"
    "If the text is already clear, return it unchanged."
)


def _numbers(text: str) -> set[str]:
    """Numeric tokens, normalised so '1,200' and '1200' are the same number."""
    found: set[str] = set()
    for token in NUMBER_RE.findall(text):
        cleaned = token.replace(",", "").rstrip(".")
        if cleaned:
            found.add(cleaned)
    return found


def introduces_new_numbers(original: str, rewrite: str) -> bool:
    """True when the rewrite contains a number the original did not have."""
    return bool(_numbers(rewrite) - _numbers(original))


def is_usable(rewrite: str, original: str) -> bool:
    """Whether a candidate rewrite may replace the grounded text."""
    candidate = rewrite.strip()
    # too short to be a rewrite, too long to be a reword, or it invented a number
    if len(candidate) < 40 or len(candidate) > len(original) * 3 + 400:
        return False
    if introduces_new_numbers(original, candidate):
        return False
    lowered = candidate.lower()
    return not any(
        marker in lowered
        for marker in ("i cannot", "i can't", "as an ai", "unable to", "<error>")
    )


async def rewrite_explanation(
    *,
    headline: str,
    body: str,
    passages: list[dict[str, Any]],
    settings: Settings,
) -> tuple[str, str]:
    """Return `(text, served_by)` for the explanation.

    `served_by` is `composed-grounded` when the deterministic text was kept and
    `composed-grounded+groq` when Groq's rewrite passed the guard.
    """
    # Only the body is rewritten. The headline is composed separately and is
    # never handed to the model, so a rewrite cannot duplicate or contradict it.
    original = body.strip()
    if not settings.groq_enabled or not settings.groq_api_key or not original:
        return original, "composed-grounded"

    evidence = "\n".join(
        f"- [{p.get('kind', 'fact')!s}] {p.get('text', '')!s}" for p in passages[:12]
    )
    user = (
        "Evidence passages:\n"
        f"{evidence}\n\n"
        f"A one-line summary of the situation, for context only - do not repeat "
        f"it:\n{headline}\n\n"
        f"Text to rewrite:\n{original}"
    )
    try:
        text = await _call_groq(
            user=user,
            api_key=settings.groq_api_key,
            base_url=settings.groq_base_url,
            model=settings.groq_model,
            request_timeout=settings.groq_timeout_seconds,
            max_tokens=settings.groq_max_tokens,
        )
    except Exception as exc:
        logger.warning("groq_rewrite_failed_keeping_grounded: %s", exc)
        record("GroqRewriteFailed", 1)
        return original, "composed-grounded"

    if not is_usable(text, original):
        logger.warning("groq_rewrite_rejected_keeping_grounded")
        record("GroqRewriteRejected", 1)
        return original, "composed-grounded"

    record("GroqRewriteUsed", 1)
    return text, "composed-grounded+groq"


async def _call_groq(
    *,
    user: str,
    api_key: str,
    base_url: str,
    model: str,
    request_timeout: float,
    max_tokens: int,
) -> str:
    from dhuan.core.http import UpstreamClient  # noqa: PLC0415

    client = UpstreamClient("groq", base_url)
    try:
        response = await client.post(
            "/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.2,
                "max_tokens": max_tokens,
            },
            timeout=request_timeout,
        )
        payload = response.json()
        choices = payload.get("choices") or []
        if not choices:
            raise ValueError("groq returned no choices")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("groq returned empty content")
        return content
    finally:
        await client.aclose()


__all__ = [
    "SYSTEM",
    "introduces_new_numbers",
    "is_usable",
    "rewrite_explanation",
]
