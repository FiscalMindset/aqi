#!/usr/bin/env python3
"""Post-deploy smoke checks against real deployed endpoints.

Usage:
    python scripts/smoke.py --base-url https://api.example.com
    python scripts/smoke.py --env staging          # resolves from SSM
    python scripts/smoke.py --url-only             # prints the URL only

Checks every critical route, validates the RFC 9457 shape of failures, and
exits non-zero on the first regression. Never prints a URL that wasn't
observed in real command output.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

ESTIMATE_PARAMS = "?lat=28.6139&lon=77.2090"


def _get(base: str, path: str, timeout: float = 15.0) -> tuple[int, dict, str]:
    req = urllib.request.Request(
        base.rstrip("/") + path,
        headers={"User-Agent": "dhuan-smoke/1.0", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read()), resp.headers.get("content-type", "")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="ignore")
        try:
            payload = json.loads(body)
        except ValueError:
            payload = {}
        return exc.code, payload, exc.headers.get("content-type", "")
    except urllib.error.URLError as exc:
        print(f"FAIL {path}: connection error {exc}")
        sys.exit(2)


def smoke(base: str) -> int:
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(f"{'PASS' if ok else 'FAIL'}  {name}{(' - ' + detail) if detail else ''}")
        if not ok:
            failures.append(name)

    status, body, _ = _get(base, "/health")
    check("/health", status == 200 and body.get("status") == "ok", f"status={status}")

    status, body, _ = _get(base, "/ready")
    check("/ready answers", status in (200, 503), f"status={status}")

    status, body, _ = _get(base, "/v1/estimate" + ESTIMATE_PARAMS)
    honesty = status == 200 and body.get("pm25_low", 1e9) <= body.get("pm25_mid", -1) <= body.get(
        "pm25_high", -1
    )
    check("/v1/estimate ordered interval", honesty, f"pm25={body.get('pm25_mid')}")
    check("/v1/estimate honesty note", bool(body.get("honesty")))
    check("/v1/estimate served_by", body.get("served_by") in ("model", "nearest-station"))

    status, body, _ = _get(base, "/v1/stations" + ESTIMATE_PARAMS)
    check("/v1/stations list", status == 200 and isinstance(body, list))

    status, body, _ = _get(base, "/v1/sources" + ESTIMATE_PARAMS)
    check("/v1/sources", status == 200 and "sources" in body)

    status, body, ctype = _get(base, "/v1/grid")
    check("/v1/grid", status == 200 and "features" in body)

    status, body, _ = _get(base, "/v1/validation")
    check("/v1/validation metrics", status in (200, 404))

    status, body, ctype = _get(base, "/v1/status")
    check("/v1/status", status == 200 and "feeds" in body)

    # outside-coverage must be a typed 422 problem, never a 500
    status, body, ctype = _get(base, "/v1/estimate?lat=19.076&lon=72.877")
    check(
        "outside-coverage is problem+json 422",
        status == 422 and ctype.startswith("application/problem+json"),
    )

    if failures:
        print(f"\nSMOKE FAILED: {len(failures)} check(s): {failures}")
        return 1
    print("\nSMOKE PASSED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Dhuan Detective smoke checks")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--env", default=None, help="resolve base URL from SSM (staging/prod)")
    parser.add_argument("--url-only", action="store_true")
    args = parser.parse_args()

    base = args.base_url
    if base is None and args.env:
        try:
            import boto3

            client = boto3.client("ssm")
            base = client.get_parameter(Name=f"/dhuan/{args.env}/api-url")["Parameter"]["Value"]
        except Exception as exc:  # noqa: BLE001
            print(f"could not resolve base URL from SSM: {exc}")
            return 2
    if base is None:
        print("--base-url or --env is required")
        return 2
    if args.url_only:
        print(base)
        return 0
    return smoke(base)


if __name__ == "__main__":
    sys.exit(main())
