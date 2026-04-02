"""OAuth2 client_credentials authentication for Timeback APIs."""

import os
import time
import requests

# Cognito token endpoint
TOKEN_URL = (
    "https://prod-beyond-timeback-api-2-idp.auth.us-east-1.amazoncognito.com"
    "/oauth2/token"
)

_cached_token = None
_token_expires_at = 0


def get_token() -> str:
    """Get a valid OAuth2 access token, refreshing if expired."""
    global _cached_token, _token_expires_at

    if _cached_token and time.time() < _token_expires_at - 60:
        return _cached_token

    client_id = os.environ["TIMEBACK_CLIENT_ID"]
    client_secret = os.environ["TIMEBACK_CLIENT_SECRET"]

    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    _cached_token = data["access_token"]
    _token_expires_at = time.time() + data.get("expires_in", 3600)

    return _cached_token


def get_session() -> requests.Session:
    """Create an authenticated requests.Session for API calls."""
    session = requests.Session()
    token = get_token()
    session.headers.update({
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    return session


def refresh_session(session: requests.Session) -> requests.Session:
    """Refresh the token on an existing session."""
    token = get_token()
    session.headers["Authorization"] = f"Bearer {token}"
    return session
