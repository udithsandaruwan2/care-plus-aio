#!/usr/bin/env python3
"""Step 71 HTTP load / concurrency harness against a running Care Plus API.

Usage (from repo root, with Docker API on :8000):

  python backend/scripts/load_step71.py --mode both
  python backend/scripts/load_step71.py --mode match --samples 50 --p95-ms 800
  python backend/scripts/load_step71.py --mode redlock --concurrency 8

Requires: seeded caregivers (or the script creates ephemeral users), Redis up,
and elevated DRF_THROTTLE_MATCH for dense match loops if needed.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

COLOMBO = ZoneInfo("Asia/Colombo")


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return float(sorted_vals[f])
    return float(sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f))


def _request(
    base: str,
    method: str,
    path: str,
    *,
    token: str | None = None,
    body: dict | None = None,
) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{base.rstrip('/')}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            payload = json.loads(raw) if raw else None
            return resp.status, payload
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            payload = json.loads(raw) if raw else {"detail": str(exc)}
        except json.JSONDecodeError:
            payload = {"detail": raw or str(exc)}
        return exc.code, payload


def _login(base: str, email: str, password: str) -> str:
    code, data = _request(
        base, "POST", "/api/v1/auth/token/", body={"email": email, "password": password}
    )
    if code != 200 or not isinstance(data, dict) or "access" not in data:
        raise SystemExit(f"login failed for {email}: {code} {data}")
    return str(data["access"])


def _next_monday_at(hour: int, minute: int = 0) -> datetime:
    now = datetime.now(tz=COLOMBO)
    days_ahead = (0 - now.weekday()) % 7
    if days_ahead == 0 and (now.hour, now.minute) >= (hour, minute):
        days_ahead = 7
    day = (now + timedelta(days=days_ahead)).date()
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=COLOMBO)


def run_match_p95(base: str, *, email: str, password: str, samples: int, p95_ms: float) -> int:
    token = _login(base, email, password)
    # Ensure AI consent (idempotent append).
    _request(
        base,
        "POST",
        "/api/v1/consent/",
        token=token,
        body={"scope": "ai_processing", "granted": True},
    )
    latencies: list[float] = []
    for i in range(samples):
        code, data = _request(
            base,
            "POST",
            "/api/v1/match/",
            token=token,
            body={
                "condition": "diabetes",
                "language": "Sinhala",
                "care_level": "intermediate",
                "longitude": 79.86,
                "latitude": 6.93,
                "k": 5,
            },
        )
        if code == 429:
            print("throttled (429) — raise DRF_THROTTLE_MATCH or slow the loop", file=sys.stderr)
            return 2
        if code not in (200, 201) or not isinstance(data, dict):
            print(f"match failed sample={i}: {code} {data}", file=sys.stderr)
            return 1
        latencies.append(float(data.get("latency_ms", 0)))

    latencies.sort()
    p95 = _percentile(latencies, 95)
    mean = statistics.mean(latencies)
    print(
        json.dumps(
            {
                "mode": "match",
                "samples": samples,
                "p95_ms": round(p95, 2),
                "mean_ms": round(mean, 2),
                "max_ms": round(latencies[-1], 2),
                "budget_ms": p95_ms,
                "pass": p95 <= p95_ms,
            },
            indent=2,
        )
    )
    return 0 if p95 <= p95_ms else 1


def run_redlock(
    base: str,
    *,
    caregiver_id: int,
    slot_id: int | None,
    patient_creds: list[tuple[str, str]],
    concurrency: int,
) -> int:
    starts = _next_monday_at(10, 0)
    ends = starts + timedelta(hours=1)
    body_base = {
        "caregiver_id": caregiver_id,
        "starts_at": starts.isoformat(),
        "ends_at": ends.isoformat(),
        "timezone": "Asia/Colombo",
    }
    if slot_id is not None:
        body_base["availability_slot_id"] = slot_id

    tokens = [_login(base, email, password) for email, password in patient_creds[:concurrency]]

    def attempt(token: str) -> int:
        code, _ = _request(base, "POST", "/api/v1/shifts/", token=token, body=body_base)
        return code

    codes: list[int] = []
    with ThreadPoolExecutor(max_workers=len(tokens)) as pool:
        futures = [pool.submit(attempt, t) for t in tokens]
        for fut in as_completed(futures):
            codes.append(fut.result())

    created = codes.count(201)
    ok = created == 1
    print(
        json.dumps(
            {
                "mode": "redlock",
                "concurrency": len(tokens),
                "codes": codes,
                "created_201": created,
                "pass": ok,
            },
            indent=2,
        )
    )
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Care Plus Step 71 load / concurrency harness")
    parser.add_argument("--base-url", default=os.environ.get("CAREPLUS_API_BASE", "http://localhost:8000"))
    parser.add_argument("--mode", choices=("match", "redlock", "both"), default="both")
    parser.add_argument("--samples", type=int, default=int(os.environ.get("MATCH_SAMPLES", "50")))
    parser.add_argument("--p95-ms", type=float, default=float(os.environ.get("MATCH_P95_MS", "800")))
    parser.add_argument(
        "--match-email",
        default=os.environ.get("LOAD_MATCH_EMAIL", ""),
        help="Patient email with AI consent for match p95",
    )
    parser.add_argument("--match-password", default=os.environ.get("LOAD_MATCH_PASSWORD", ""))
    parser.add_argument("--concurrency", type=int, default=int(os.environ.get("BOOK_CONCURRENCY", "8")))
    parser.add_argument("--caregiver-id", type=int, default=int(os.environ.get("LOAD_CAREGIVER_ID", "0")))
    parser.add_argument("--slot-id", type=int, default=int(os.environ.get("LOAD_SLOT_ID", "0")))
    parser.add_argument(
        "--patient-creds",
        default=os.environ.get("LOAD_PATIENT_CREDS", ""),
        help="Comma-separated email:password pairs for concurrent booking",
    )
    args = parser.parse_args(argv)

    rc = 0
    if args.mode in ("match", "both"):
        if not args.match_email or not args.match_password:
            print(
                "match mode needs --match-email/--match-password "
                "(or LOAD_MATCH_EMAIL / LOAD_MATCH_PASSWORD)",
                file=sys.stderr,
            )
            return 2
        rc |= run_match_p95(
            args.base_url,
            email=args.match_email,
            password=args.match_password,
            samples=args.samples,
            p95_ms=args.p95_ms,
        )

    if args.mode in ("redlock", "both"):
        if not args.caregiver_id or not args.patient_creds:
            print(
                "redlock mode needs --caregiver-id and --patient-creds "
                "(email:password,...)",
                file=sys.stderr,
            )
            return 2
        pairs = []
        for part in args.patient_creds.split(","):
            email, _, password = part.partition(":")
            if not email or not password:
                print(f"bad patient cred: {part}", file=sys.stderr)
                return 2
            pairs.append((email.strip(), password.strip()))
        rc |= run_redlock(
            args.base_url,
            caregiver_id=args.caregiver_id,
            slot_id=args.slot_id or None,
            patient_creds=pairs,
            concurrency=args.concurrency,
        )
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
