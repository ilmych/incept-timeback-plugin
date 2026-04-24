# Cognito OAuth2 Authentication (for Read APIs)

**Scope:** all read-side endpoints — OneRoster, EduBridge, PowerPath, QTI (verified 2026-04-23 across 40+ student pulls).

The QTI creation endpoints use the same token. The creation skills don't document this explicitly, so first-time integrators often re-implement auth wrong.

## Endpoint

```
POST https://prod-beyond-timeback-api-2-idp.auth.us-east-1.amazoncognito.com/oauth2/token
```

Override via `TIMEBACK_TOKEN_URL` env var if a different environment is provisioned.

## Grant Type

**`client_credentials`** (M2M). No user flow, no redirect URI, no PKCE.

You receive a client ID + secret out-of-band from the Timeback team. They go in env vars — never in code, never in the repo.

```bash
export TIMEBACK_CLIENT_ID="..."
export TIMEBACK_CLIENT_SECRET="..."
export TIMEBACK_BASE_URL="https://api.alpha-1edtech.ai"    # OneRoster / EduBridge / PowerPath (optional override)
export TIMEBACK_QTI_BASE="https://qti.alpha-1edtech.ai"    # QTI (optional override)
```

## Token Exchange (Python)

```python
import requests, os

def get_token() -> str:
    r = requests.post(
        os.environ.get("TIMEBACK_TOKEN_URL",
            "https://prod-beyond-timeback-api-2-idp.auth.us-east-1.amazoncognito.com/oauth2/token"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "client_credentials",
            "client_id": os.environ["TIMEBACK_CLIENT_ID"],
            "client_secret": os.environ["TIMEBACK_CLIENT_SECRET"],
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]
```

Response shape:

```json
{
  "access_token": "eyJ...",
  "expires_in": 3600,
  "token_type": "Bearer"
}
```

## Using the Token

Every API call goes out with:

```
Authorization: Bearer <access_token>
```

## Token Caching (important for bulk pulls)

A fresh token costs ~200ms. For a 40-student × 7-subject × 40-week pull that's 11,200 calls — do NOT fetch a new token per call. Cache and reuse until 60s before `expires_in`.

```python
import asyncio, os, time, httpx

class TokenCache:
    def __init__(self):
        self.token: str | None = None
        self.expires_at = 0
        self.lock = asyncio.Lock()

    async def get(self, client: httpx.AsyncClient) -> str:
        async with self.lock:
            if self.token and time.time() < self.expires_at - 60:
                return self.token
            r = await client.post(
                os.environ.get("TIMEBACK_TOKEN_URL",
                    "https://prod-beyond-timeback-api-2-idp.auth.us-east-1.amazoncognito.com/oauth2/token"),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={"grant_type": "client_credentials",
                      "client_id": os.environ["TIMEBACK_CLIENT_ID"],
                      "client_secret": os.environ["TIMEBACK_CLIENT_SECRET"]},
                timeout=30,
            )
            r.raise_for_status()
            d = r.json()
            self.token = d["access_token"]
            self.expires_at = time.time() + d["expires_in"]
            return self.token
```

The 60-second buffer avoids "just expired" races mid-request.

## Retry / Backoff

Transient 5xx and 429 are common under load. Same pattern as the QTI skill:

- Retry on: `{429, 500, 502, 503, 504}`
- Backoff: `[5, 15, 30]` seconds (3 retries)
- Do NOT retry on 4xx other than 429 — they're contract errors
- **401 special-case**: evict the cached token, force a refresh, retry once. Cognito can revoke mid-run or the run can exceed `expires_in` despite the 60s buffer (clock drift, long-running pulls). Without this branch every call after revocation silently returns 401.

```python
RETRY_CODES = {429, 500, 502, 503, 504}
RETRY_BACKOFF = [5, 15, 30]

async def get_with_retry(client, cache, url, params=None, timeout=30):
    refreshed_once = False
    for attempt in range(len(RETRY_BACKOFF) + 1):
        token = await cache.get(client)
        try:
            r = await client.get(url, params=params,
                                 headers={"Authorization": f"Bearer {token}"},
                                 timeout=timeout)
            # 401: token revoked or expired beyond the 60s buffer.
            # Evict and retry exactly once — avoid infinite refresh loops
            # on a genuinely bad client_id/secret.
            if r.status_code == 401 and not refreshed_once:
                cache.expires_at = 0          # force refresh on next get()
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
```

## Common Failures

| Symptom | Cause | Fix |
|---|---|---|
| 401 on every call after a long run | Token revoked or expired beyond the 60s buffer, wrapper doesn't refresh | Add the 401 branch in `get_with_retry` shown above (evict cache, refresh once, retry) — the 60s buffer alone is insufficient for runs that exceed `expires_in` |
| 403 on creation endpoints, 200 on reads | Client has read-only scope | Request write scope from Timeback team; not a code bug |
| `invalid_client` from token endpoint | Whitespace in `TIMEBACK_CLIENT_SECRET` env var | Strip the env var; no leading/trailing spaces |
| 429 storms during bulk pull | No semaphore, hundreds of parallel calls | Wrap calls in `asyncio.Semaphore(10)` — that's the observed safe ceiling |
| Token works for `api.alpha-1edtech.ai` but fails on `qti.alpha-1edtech.ai` | None — the same token works on both (verified 2026-04-23) | Check for a typo or stale copy of the token |
