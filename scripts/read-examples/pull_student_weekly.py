#!/usr/bin/env python3
"""Minimal example: pull one week of analytics for one student.

Demonstrates the core read pattern used across all Timeback read APIs:
  1. Cognito client_credentials token exchange
  2. Retry/backoff on transient 5xx + 429
  3. Three endpoints combined into one snapshot:
       - EduBridge weekly facts   (XP/mastery rollup)
       - OneRoster classes        (current enrollments)
       - PowerPath subject progress (per-course XP totals)

READ-ONLY. Only HTTP GET calls (plus one POST to /oauth2/token for auth).
No data is created, updated, or deleted in Timeback.

Usage:
    export TIMEBACK_CLIENT_ID="..."
    export TIMEBACK_CLIENT_SECRET="..."
    python3 pull_student_weekly.py <student_sourced_id> <week_sunday_iso>

Example:
    python3 pull_student_weekly.py stu-abc123 2026-04-13
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time

import httpx

# ── Config ─────────────────────────────────────────────────────────────────
BASE_URL = os.environ.get("TIMEBACK_BASE_URL", "https://api.alpha-1edtech.ai")
TOKEN_URL = os.environ.get(
    "TIMEBACK_TOKEN_URL",
    "https://prod-beyond-timeback-api-2-idp.auth.us-east-1.amazoncognito.com/oauth2/token",
)
CLIENT_ID = os.environ["TIMEBACK_CLIENT_ID"]
CLIENT_SECRET = os.environ["TIMEBACK_CLIENT_SECRET"]

SUBJECTS = ["math", "reading", "language", "science", "writing", "vocabulary"]
RETRY_CODES = {429, 500, 502, 503, 504}
RETRY_BACKOFF = [5, 15, 30]


# ── Auth ───────────────────────────────────────────────────────────────────
class TokenCache:
    def __init__(self) -> None:
        self.token: str | None = None
        self.expires_at: float = 0
        self.lock = asyncio.Lock()

    async def get(self, client: httpx.AsyncClient) -> str:
        async with self.lock:
            if self.token and time.time() < self.expires_at - 60:
                return self.token
            r = await client.post(
                TOKEN_URL,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "client_credentials",
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                },
                timeout=30,
            )
            r.raise_for_status()
            d = r.json()
            self.token = d["access_token"]
            self.expires_at = time.time() + d["expires_in"]
            return self.token


# ── Retry wrapper ──────────────────────────────────────────────────────────
async def get_with_retry(client, cache, url, params=None, timeout=30) -> dict:
    refreshed_once = False
    for attempt in range(len(RETRY_BACKOFF) + 1):
        token = await cache.get(client)
        try:
            r = await client.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
                timeout=timeout,
            )
            # 401: token revoked or expired beyond the 60s buffer. Evict and
            # retry exactly once — avoid infinite refresh loops on bad creds.
            if r.status_code == 401 and not refreshed_once:
                cache.expires_at = 0
                refreshed_once = True
                continue
            if r.status_code in RETRY_CODES and attempt < len(RETRY_BACKOFF):
                await asyncio.sleep(RETRY_BACKOFF[attempt])
                continue
            if r.status_code == 200:
                return {"ok": True, "data": r.json()}
            return {"ok": False, "status": r.status_code, "error": r.text[:500]}
        except Exception as e:
            if attempt < len(RETRY_BACKOFF):
                await asyncio.sleep(RETRY_BACKOFF[attempt])
                continue
            return {"ok": False, "error": str(e)}
    return {"ok": False, "error": "retry exhausted"}


# ── Fetchers ───────────────────────────────────────────────────────────────
async def fetch_weekly_facts(client, cache, sid, week):
    return await get_with_retry(
        client, cache,
        f"{BASE_URL}/edubridge/analytics/facts/weekly",
        params={"studentId": sid, "weekDate": week, "timezone": "America/Chicago"},
    )


async def fetch_classes(client, cache, sid):
    return await get_with_retry(
        client, cache,
        f"{BASE_URL}/ims/oneroster/rostering/v1p2/students/{sid}/classes",
        params={"limit": 500},
    )


async def fetch_subject_progress(client, cache, sid, subject):
    return await get_with_retry(
        client, cache,
        f"{BASE_URL}/powerpath/placement/getSubjectProgress",
        params={"student": sid, "subject": subject},     # NB: "student", not "studentId"
        timeout=45,
    )


def filter_meaningful_courses(progress_data: dict) -> list[dict]:
    """Drop the ~2000 catalog courses the student has never touched."""
    prog = progress_data.get("progress", [])
    return [
        p for p in prog
        if p.get("inEnrolled") or (p.get("totalXpEarned") or 0) > 0
    ]


# ── Main ───────────────────────────────────────────────────────────────────
async def main(sid: str, week: str):
    cache = TokenCache()
    async with httpx.AsyncClient() as client:
        # Fire everything in parallel
        weekly_task = fetch_weekly_facts(client, cache, sid, week)
        classes_task = fetch_classes(client, cache, sid)
        progress_tasks = [
            fetch_subject_progress(client, cache, sid, s) for s in SUBJECTS
        ]
        weekly, classes, *progress_results = await asyncio.gather(
            weekly_task, classes_task, *progress_tasks,
        )

    snapshot = {
        "student_id": sid,
        "week": week,
        "pulled_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "weekly_facts": weekly.get("data") if weekly["ok"] else {"error": weekly},
        "current_classes": (
            classes["data"].get("classes", []) if classes["ok"] else []
        ),
        "subject_progress": {
            subject: filter_meaningful_courses(r["data"]) if r["ok"] else []
            for subject, r in zip(SUBJECTS, progress_results)
        },
    }
    print(json.dumps(snapshot, indent=2, default=str))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2]))
