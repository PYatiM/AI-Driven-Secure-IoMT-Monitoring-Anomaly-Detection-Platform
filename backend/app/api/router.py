from fastapi import APIRouter

from backend.app.api.routes.alerts import router as alerts_router
from backend.app.api.routes.auth import router as auth_router
from backend.app.api.routes.devices import router as devices_router
from backend.app.api.routes.monitoring import router as monitoring_router
from backend.app.api.routes.telemetry import router as telemetry_router
from backend.app.api.routes.users import router as users_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(monitoring_router)
api_router.include_router(alerts_router)
api_router.include_router(devices_router)
api_router.include_router(telemetry_router)
