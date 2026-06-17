# ========= Copyright 2025-2026 @ Eigent.ai All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ========= Copyright 2025-2026 @ Eigent.ai All Rights Reserved. =========

"""
Cognito Hosted UI login for self-hosted web.

Flow (Authorization Code, backend-driven):
  GET /auth/cognito/login    -> 302 to Cognito Hosted UI (signed state carries return origin)
  GET /auth/cognito/callback -> exchange code, verify id_token, upsert user, mint Eigent JWT,
                                302 to <frontend>/login?token=<jwt>
"""

import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode

import jwt
from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from loguru import logger
from sqlmodel import Session

from app.core import cognito
from app.core.database import session
from app.core.environment import env, env_not_empty
from app.model.user.user import Status, User
from app.shared.auth import create_access_token
from app.shared.auth.user_auth import SECRET_KEY

router = APIRouter(prefix="/auth/cognito", tags=["Cognito Auth"])

_STATE_TTL = timedelta(minutes=10)
_STATE_TYPE = "cognito_state"


def _allowed_frontends() -> list[str]:
    """Allowlist of frontend origins we may redirect back to (comma-separated env)."""
    raw = env_not_empty("frontend_url")
    return [u.strip().rstrip("/") for u in raw.split(",") if u.strip()]


def _resolve_redirect(requested: str | None) -> str:
    """Return a safe frontend origin: the requested one if allowlisted, else the first allowed."""
    allowed = _allowed_frontends()
    if requested:
        candidate = requested.rstrip("/")
        if candidate in allowed:
            return candidate
        logger.warning("Cognito login redirect not in allowlist, falling back", extra={"requested": requested})
    return allowed[0]


def _encode_state(redirect: str) -> str:
    payload = {
        "type": _STATE_TYPE,
        "nonce": secrets.token_urlsafe(16),
        "redirect": redirect,
        "exp": datetime.utcnow() + _STATE_TTL,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def _decode_state(state: str) -> str:
    """Validate the signed state and return the carried redirect origin."""
    payload = jwt.decode(state, SECRET_KEY, algorithms=["HS256"])
    if payload.get("type") != _STATE_TYPE:
        raise jwt.InvalidTokenError("Invalid state type")
    return _resolve_redirect(payload.get("redirect"))


def _error_redirect(redirect: str, message: str) -> RedirectResponse:
    return RedirectResponse(f"{redirect}/login?{urlencode({'auth_error': message})}")


def _upsert_user(claims: dict, db_session: Session) -> User:
    """Find a user by Cognito email (or sub) and create/link it if needed."""
    email = claims.get("email")
    sub = claims.get("sub")
    if not email:
        raise ValueError("Cognito id_token has no email claim")

    user = User.by(User.email == email, s=db_session).one_or_none()
    if user is None:
        user = User.by(User.stack_id == sub, s=db_session).one_or_none()

    with db_session as s:
        if user is None:
            user = User(
                email=email,
                stack_id=sub,
                username=email,
                nickname=claims.get("name") or email.split("@")[0],
                avatar="",
                fullname=claims.get("name") or "",
                work_desc="",
            )
            s.add(user)
        elif not user.stack_id:
            user.stack_id = sub
            s.add(user)
        s.commit()
        s.refresh(user)
    return user


@router.get("/login", name="Cognito Login Redirect")
def cognito_login(redirect: str | None = Query(default=None)):
    """Redirect the browser to the Cognito Hosted UI authorize endpoint."""
    target = _resolve_redirect(redirect)
    state = _encode_state(target)
    return RedirectResponse(cognito.build_authorize_url(state))


@router.get("/logout", name="Cognito Logout Redirect")
def cognito_logout(redirect: str | None = Query(default=None)):
    """Destroy the Cognito Hosted UI session so the next login prompts for credentials.

    Local app logout only clears the Eigent JWT; without this the pool's session
    cookie would silently re-authenticate the same user. We send the browser to
    Cognito's /logout, which clears that cookie and returns to <frontend>/login.
    """
    target = _resolve_redirect(redirect)
    return RedirectResponse(cognito.build_logout_url(f"{target}/login"))


@router.get("/callback", name="Cognito Callback")
def cognito_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
    db_session: Session = Depends(session),
):
    """Handle the Cognito redirect: exchange code, verify token, mint Eigent JWT."""
    # Resolve the return origin from the signed state (falls back to allowlist default).
    try:
        redirect = _decode_state(state) if state else _resolve_redirect(None)
    except jwt.InvalidTokenError:
        logger.warning("Cognito callback with invalid state")
        return _error_redirect(_resolve_redirect(None), "invalid_state")

    if error:
        logger.warning("Cognito returned an error", extra={"error": error, "desc": error_description})
        return _error_redirect(redirect, error)
    if not code:
        return _error_redirect(redirect, "missing_code")

    try:
        tokens = cognito.exchange_code(code)
        id_token = tokens.get("id_token")
        if not id_token:
            raise ValueError("No id_token in token response")
        claims = cognito.verify_id_token(id_token)
    except Exception as e:
        logger.error("Cognito token exchange/verify failed", extra={"error": str(e)}, exc_info=True)
        return _error_redirect(redirect, "auth_failed")

    try:
        user = _upsert_user(claims, db_session)
    except Exception as e:
        logger.error("Cognito user upsert failed", extra={"error": str(e)}, exc_info=True)
        return _error_redirect(redirect, "user_error")

    if user.status == Status.Block:
        return _error_redirect(redirect, "account_blocked")

    app_token = create_access_token(user.id)
    logger.info("Cognito login successful", extra={"user_id": user.id, "email": user.email})
    return RedirectResponse(f"{redirect}/login?{urlencode({'token': app_token})}")
