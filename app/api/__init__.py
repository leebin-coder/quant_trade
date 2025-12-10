"""API application entrypoint."""
from fastapi import FastAPI

from app.core.config import settings
from app.api.websocket import router as websocket_router

api_app = FastAPI(
    title=f"{settings.project_name} API",
    version=settings.version,
    description="Quant Trade WebSocket API surface",
)

# WebSocket endpoints live under /ws
api_app.include_router(websocket_router, prefix="/ws")

__all__ = ["api_app"]
