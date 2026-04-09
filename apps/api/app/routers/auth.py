"""
Google OAuth 2.0 authentication router.

Flow:
  1. Browser hits GET /auth/login  → redirected to Google consent screen
  2. Google redirects to GET /auth/callback?code=...
  3. We exchange the code for user info, upsert the user in DB,
     issue a signed JWT in an HttpOnly cookie, and redirect to the frontend.
  4. GET /auth/me returns the current user (or 401).
  5. GET /auth/logout clears the cookie.

Required environment variables:
  GOOGLE_CLIENT_ID      — from Google Cloud Console (OAuth 2.0 credentials)
  GOOGLE_CLIENT_SECRET  — from Google Cloud Console
  SECRET_KEY            — any long random string for signing JWT cookies
  FRONTEND_URL          — e.g. https://aqua-sense-ai.vercel.app (no trailing slash)

All three are optional at startup — auth endpoints simply return 503
if they are not configured, so the rest of the app keeps working.
"""

import os
import json
import logging
import time
from typing import Optional

import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

logger = logging.getLogger("auth")
router = APIRouter(prefix="/auth", tags=["auth"])

# ── Config ────────────────────────────────────────────────────────────────────
_GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_INFO_URL  = "https://www.googleapis.com/oauth2/v3/userinfo"
_SCOPES           = "openid email profile"
_COOKIE_NAME      = "aq_session"
_COOKIE_MAX_AGE   = 60 * 60 * 24 * 30  # 30 days


def _cfg():
    client_id     = os.environ.get("GOOGLE_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    secret_key    = os.environ.get("SECRET_KEY", "")
    frontend_url  = os.environ.get("FRONTEND_URL", "http://localhost:3001").rstrip("/")
    return client_id, client_secret, secret_key, frontend_url


def _serializer(secret_key: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key, salt="aq-session")


def _make_cookie(response, secret_key: str, payload: dict) -> None:
    token = _serializer(secret_key).dumps(payload)
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="lax",
    )


def _clear_cookie(response) -> None:
    response.delete_cookie(_COOKIE_NAME, httponly=True, secure=True, samesite="lax")


def get_current_user(request: Request) -> Optional[dict]:
    """Extract and validate the session cookie. Returns user dict or None."""
    _, _, secret_key, _ = _cfg()
    if not secret_key:
        return None
    token = request.cookies.get(_COOKIE_NAME)
    if not token:
        return None
    try:
        return _serializer(secret_key).loads(token, max_age=_COOKIE_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/login")
def login(request: Request):
    """Redirect the browser to Google's OAuth consent screen."""
    client_id, _, _, frontend_url = _cfg()
    if not client_id:
        raise HTTPException(status_code=503, detail="Google OAuth not configured")

    callback_url = str(request.base_url).rstrip("/") + "/auth/callback"
    params = (
        f"client_id={client_id}"
        f"&redirect_uri={callback_url}"
        f"&response_type=code"
        f"&scope={_SCOPES.replace(' ', '%20')}"
        f"&access_type=offline"
        f"&prompt=select_account"
    )
    return RedirectResponse(f"{_GOOGLE_AUTH_URL}?{params}")


@router.get("/callback")
async def callback(request: Request, code: str = "", error: str = ""):
    """Handle the OAuth redirect from Google."""
    client_id, client_secret, secret_key, frontend_url = _cfg()
    if not client_id or not client_secret or not secret_key:
        raise HTTPException(status_code=503, detail="Google OAuth not configured")

    if error or not code:
        return RedirectResponse(f"{frontend_url}?auth_error=cancelled")

    callback_url = str(request.base_url).rstrip("/") + "/auth/callback"

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(_GOOGLE_TOKEN_URL, data={
            "code":          code,
            "client_id":     client_id,
            "client_secret": client_secret,
            "redirect_uri":  callback_url,
            "grant_type":    "authorization_code",
        })

    if token_resp.status_code != 200:
        logger.warning(f"Token exchange failed: {token_resp.text}")
        return RedirectResponse(f"{frontend_url}?auth_error=token_failed")

    access_token = token_resp.json().get("access_token")
    if not access_token:
        return RedirectResponse(f"{frontend_url}?auth_error=no_token")

    # Fetch user info
    async with httpx.AsyncClient() as client:
        info_resp = await client.get(
            _GOOGLE_INFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if info_resp.status_code != 200:
        return RedirectResponse(f"{frontend_url}?auth_error=userinfo_failed")

    info = info_resp.json()
    google_id = info.get("sub")
    email     = info.get("email")
    if not google_id or not email:
        return RedirectResponse(f"{frontend_url}?auth_error=missing_info")

    # Upsert user in DB
    try:
        try:
            from apps.api.app.database import upsert_user
        except ImportError:
            from app.database import upsert_user  # type: ignore[import]
        user = upsert_user(
            google_id = google_id,
            email     = email,
            name      = info.get("name"),
            picture   = info.get("picture"),
        )
    except Exception as e:
        logger.warning(f"upsert_user failed: {e}")
        user = {"id": 0, "email": email, "name": info.get("name"), "picture": info.get("picture")}

    # Issue session cookie and redirect home
    payload = {
        "id":      user.get("id") if user else 0,
        "email":   email,
        "name":    info.get("name"),
        "picture": info.get("picture"),
        "iat":     int(time.time()),
    }
    response = RedirectResponse(f"{frontend_url}?auth=success")
    _make_cookie(response, secret_key, payload)
    return response


@router.get("/me")
def me(request: Request):
    """Return the current logged-in user, or 401."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {
        "id":      user.get("id"),
        "email":   user.get("email"),
        "name":    user.get("name"),
        "picture": user.get("picture"),
    }


@router.get("/logout")
def logout():
    """Clear the session cookie and redirect to home."""
    _, _, _, frontend_url = _cfg()
    response = RedirectResponse(frontend_url or "/")
    _clear_cookie(response)
    return response
