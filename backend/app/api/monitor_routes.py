"""Demo-only synthetic money-flow simulator and graph snapshot endpoints."""
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.database import get_session
from app.core.security import current_user
from app.services.ledger import get_owner
from app.services.simulator import graph_snapshot, reset_simulated_data, runner
from app.sockets.server import sio

router = APIRouter(prefix="/api", tags=["Live simulation"])


def only_dev():
    if settings.app_env.lower() != "development":
        raise HTTPException(404, detail="Demo simulation disabled outside development")


class StartSettings(BaseModel):
    interval_seconds: int = Field(default=3, ge=2, le=10)


class ResetSettings(BaseModel):
    confirm: str


@router.get('/monitor/graph')
def network(limit: int = Query(320, ge=20, le=500), user: dict = Depends(current_user), db: Session = Depends(get_session)):
    return graph_snapshot(db, get_owner(user), limit)


@router.get('/simulation/status')
async def status(user: dict = Depends(current_user)):
    only_dev()
    return runner.status(get_owner(user))


@router.post('/simulation/start')
async def start(body: StartSettings, user: dict = Depends(current_user)):
    only_dev()
    return await runner.start(get_owner(user), body.interval_seconds)


@router.post('/simulation/stop')
async def stop(user: dict = Depends(current_user)):
    only_dev()
    return await runner.stop(get_owner(user))


@router.post('/simulation/reset')
async def reset(body: ResetSettings, user: dict = Depends(current_user)):
    only_dev()
    owner = get_owner(user)
    if runner.status(owner)['running']:
        raise HTTPException(409, detail="Stop the simulation before resetting")
    if body.confirm != 'RESET_SIMULATION':
        raise HTTPException(422, detail="Explicit reset confirmation required")
    deleted = await run_in_threadpool(reset_simulated_data, owner)
    await sio.emit('simulation_reset', {"deleted": deleted}, to=f"user:{owner}")
    return {"deleted": deleted}
