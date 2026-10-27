import socketio

from app.core.config import settings
from app.core.security import AuthUnavailable, InvalidToken, verify_supabase_token

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
    except (AuthUnavailable, InvalidToken):
        raise socketio.exceptions.ConnectionRefusedError("Invalid or unavailable authentication")

    # Server controls rooms; clients can never join another user's room.
    await sio.enter_room(sid, f"user:{user['id']}")


@sio.event
async def disconnect(sid, reason=None):
    return None
