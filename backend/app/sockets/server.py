import logging

import socketio

from app.core.config import settings
from app.core.security import AuthUnavailable, InvalidToken, verify_supabase_token

log = logging.getLogger(__name__)

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=[settings.frontend_origin],
    logger=False,
    engineio_logger=False,
)


@sio.event
async def connect(sid, environ, auth):
    token = auth.get("token") if isinstance(auth, dict) else None
    if not isinstance(token, str) or not token:
        raise socketio.exceptions.ConnectionRefusedError("Authentication required")
    try:
        user = await verify_supabase_token(token)
    except InvalidToken as exc:
        # Never log the access token or return token contents to the browser.
        log.warning("Socket.IO authentication rejected: %s", exc)
        raise socketio.exceptions.ConnectionRefusedError(
            "Invalid or expired Supabase access token. Sign out and sign in again; verify both apps use the same Supabase project."
        ) from exc
    except AuthUnavailable as exc:
        log.error("Socket.IO cannot verify Supabase authentication: %s", exc)
        raise socketio.exceptions.ConnectionRefusedError(
            "Backend Supabase authentication unavailable. Check SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY in backend/.env, then restart FastAPI."
        ) from exc

    # Server controls rooms; clients can never join another user's room.
    await sio.enter_room(sid, f"user:{user['id']}")


@sio.event
async def disconnect(sid, reason=None):
    return None
