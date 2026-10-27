"""Authenticated ML analysis and investigation alerts."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.database import get_session
from app.core.security import current_user
from app.detection.engine import analyze_and_persist, list_alerts
from app.detection.model import MODEL_VERSION, reference_model
from app.services.ledger import get_owner
from app.sockets.server import sio

router=APIRouter(prefix='/api/detection',tags=['ML fraud detection'])

@router.get('/status')
def status(user:dict=Depends(current_user)):
    reference_model()  # Ensure the trained model is genuinely ready.
    return {'model':'ExtraTreesClassifier','version':MODEL_VERSION,'ready':True,
            'training_data':'separate synthetic training and calibration sets',
            'limitations':'Supervised synthetic pattern screening; not real-world-calibrated fraud probability'}

@router.get('/alerts')
def alerts(limit:int=Query(60,ge=1,le=100),user:dict=Depends(current_user),db:Session=Depends(get_session)):
    return {'items':list_alerts(db,get_owner(user),limit)}

@router.post('/analyze')
async def analyze(user:dict=Depends(current_user)):
    owner=get_owner(user)
    def run():
        from app.core.database import get_engine
        with Session(get_engine()) as db:
            return analyze_and_persist(db,owner)
    fresh=await run_in_threadpool(run)
    for alert in fresh:
        await sio.emit('fraud_alert_detected',alert,to=f'user:{owner}')
    return {'new_alerts':len(fresh),'alerts':fresh}
