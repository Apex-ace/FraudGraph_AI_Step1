"""Analytics, functional synthetic model benchmark, and guided demo."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.database import get_session
from app.core.security import current_user
from app.services.ledger import get_owner
from app.services.intelligence import intelligence_overview, evaluate_synthetic_scenarios
from app.services.demo_case import prepare_case
from app.services.simulator import runner
from app.sockets.server import sio

router = APIRouter(prefix='/api/intelligence', tags=['Fraud intelligence'])

@router.get('/overview')
def overview(user: dict = Depends(current_user), db: Session = Depends(get_session)):
    return intelligence_overview(db, get_owner(user))

@router.get('/evaluation')
async def evaluation(user: dict = Depends(current_user)):
    return await run_in_threadpool(evaluate_synthetic_scenarios)

@router.post('/demo/prepare')
async def demo_prepare(user: dict = Depends(current_user)):
    if settings.app_env.lower() != 'development':
        raise HTTPException(404, detail='Guided simulation is disabled outside development')
    owner = get_owner(user)
    if runner.status(owner)['running']:
        raise HTTPException(409, detail='Stop the live simulator before creating a guided case')
    result = await run_in_threadpool(prepare_case, owner)
    for alert in result['new_alerts']:
        await sio.emit('fraud_alert_detected', alert, to=f'user:{owner}')
    if result['created_transactions']:
        await sio.emit('simulation_status', {'guided_demo_created': result['created_transactions']}, to=f'user:{owner}')
    return result
