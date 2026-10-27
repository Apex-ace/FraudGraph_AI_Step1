from typing import Any
import logging

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

log = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)


class InvalidToken(Exception):
    pass


class AuthUnavailable(Exception):
    pass


async def verify_supabase_token(token: str) -> dict[str, Any]:
    """Verify the bearer token with Supabase Auth, never by decoding it unverified."""
    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise AuthUnavailable("Supabase authentication has not been configured")
    if "YOUR_PROJECT" in settings.supabase_url or "YOUR_KEY" in settings.supabase_publishable_key:
        raise AuthUnavailable("Update backend/.env with actual Supabase credentials")
    if not token:
        raise InvalidToken("Missing access token")

    url = settings.supabase_url.rstrip("/") + "/auth/v1/user"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(
                url,
                headers={
                    "apikey": settings.supabase_publishable_key,
                    "Authorization": f"Bearer {token}",
                },
            )
    except httpx.RequestError as exc:
        raise AuthUnavailable("Supabase Auth cannot be reached") from exc

    if response.status_code != 200:
        # Do not include response body, credentials, or tokens in logs.
        log.warning("Supabase Auth GET /auth/v1/user returned HTTP %s", response.status_code)
    if response.status_code in (401, 403):
        raise InvalidToken("Invalid or expired Supabase access token")
    if response.status_code != 200:
        raise AuthUnavailable("Supabase authentication could not be verified")

    try:
        user = response.json()
    except ValueError as exc:
        raise AuthUnavailable("Unexpected response from Supabase Auth") from exc
    if not isinstance(user, dict) or not user.get("id"):
        raise InvalidToken("User identity is missing")
    return user


async def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        return await verify_supabase_token(credentials.credentials)
    except InvalidToken as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except AuthUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
