from fastapi import APIRouter

from backend.app.api.routes.devices import router as devices_router
from backend.app.api.routes.telemetry import router as telemetry_router

api_router = APIRouter()
api_router.include_router(devices_router)
api_router.include_router(telemetry_router)
