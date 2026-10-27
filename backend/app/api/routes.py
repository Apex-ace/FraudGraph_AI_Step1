import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.database import test_database_connection
from app.core.security import current_user
from app.sockets.server import sio

router = APIRouter(prefix="/api")
log = logging.getLogger(__name__)


class LocalCredentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


def only_local():
    if settings.auth_mode.lower() != 'local':
        raise HTTPException(404, detail='Local authentication is disabled')


@router.post('/auth/register', status_code=201)
def register_local(value: LocalCredentials):
    only_local()
    from app.core.local_auth import register_user
    return register_user(value.email, value.password)


@router.post('/auth/login')
def login_local(value: LocalCredentials):
    only_local()
    from app.core.local_auth import login_user
    return login_user(value.email, value.password)


class DemoNotification(BaseModel):
    message: str = "Suspicious circular transfer detected (demo only)"


@router.get("/health")
async def health():
    return {"status": "ok", "service": "fraudgraph-api", "stage": "local-sqlite"}


@router.get("/me")
async def me(user: dict = Depends(current_user)):
    return {"id": user["id"], "email": user.get("email")}


@router.get("/health/database")
async def database_health(user: dict = Depends(current_user)):
    try:
        ok = await run_in_threadpool(test_database_connection)
    except Exception:
        log.exception("Database connectivity check failed")
        raise HTTPException(status_code=503, detail="Database unavailable. Check backend configuration and logs.")
    return {"status": "connected" if ok else "unavailable", "database": ("sqlite-local" if settings.db_provider.lower() == "sqlite" else "postgresql")}


@router.post("/demo/notify")
async def send_test_alert(payload: DemoNotification, user: dict = Depends(current_user)):
    if settings.app_env.lower() != "development":
        raise HTTPException(status_code=404, detail="Not found")
    event = {
        "id": str(uuid4()),
        "type": "demo_only",
        "title": "Demo notification",
        "message": payload.message[:220],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await sio.emit("fraud_alert_demo", event, to=f"user:{user['id']}")
    return {"sent": True, "event": event}
