import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings
from app.sockets.server import sio

api = FastAPI(title="FraudGraph AI API", version="0.1.0")
api.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
api.include_router(router)

# FastAPI routes and Socket.IO share localhost:8000.
app = socketio.ASGIApp(sio, other_asgi_app=api)
