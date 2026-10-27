import socketio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.api.ledger_routes import router as ledger_router
from app.api.monitor_routes import router as monitor_router
from app.services.simulator import runner
from app.core.config import settings
from app.sockets.server import sio

@asynccontextmanager
async def lifespan(_app):
    yield
    await runner.close()


api = FastAPI(title="FraudGraph AI API", version="0.2.1", lifespan=lifespan)
api.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
api.include_router(router)
api.include_router(ledger_router)
api.include_router(monitor_router)

# FastAPI routes and Socket.IO share localhost:8000.
app = socketio.ASGIApp(sio, other_asgi_app=api)
