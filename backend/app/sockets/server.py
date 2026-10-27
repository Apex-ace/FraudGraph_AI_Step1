import logging

import socketio

from app.core.config import settings
from app.core.security import AuthUnavailable, InvalidToken, verify_access_token

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
        user = await verify_access_token(token)
    except InvalidToken as exc:
        # Never log the access token or return token contents to the browser.
        log.warning("Socket.IO authentication rejected: %s", exc)
        raise socketio.exceptions.ConnectionRefusedError(
            "Invalid or expired access token. Please sign in again."
        ) from exc
    except AuthUnavailable as exc:
        log.error("Socket.IO cannot verify authentication: %s", exc)
        raise socketio.exceptions.ConnectionRefusedError(
            "Authentication unavailable. Review AUTH_MODE settings and backend logs."
        ) from exc

    # Server controls rooms; clients can never join another user's room.
    await sio.enter_room(sid, f"user:{user['id']}")


@sio.event
async def disconnect(sid, reason=None):
    return None
