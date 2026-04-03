import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.app.api.router import api_router
from backend.app.api.routes.health import router as health_router
from backend.app.core.config import get_settings
from backend.app.core.logging import configure_logging
from backend.app.middleware import (
    AuthenticationMiddleware,
    HTTPSMiddleware,
    RequestValidationMiddleware,
)

settings = get_settings()
configure_logging(settings.log_level)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info(
        "Starting %s in %s mode",
        settings.app_name,
        settings.app_env,
    )
    logger.info(
        "PostgreSQL configured for %s:%s/%s",
        settings.db_host,
        settings.db_port,
        settings.db_name,
    )
    logger.info("HTTPS enforcement enabled: %s", settings.https_enforced)
    logger.info("API request validation enabled: %s", settings.api_validate_requests)
    yield
    logger.info("Shutting down %s", settings.app_name)


async def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    errors = [
        {
            "location": list(error.get("loc", ())),
            "message": error.get("msg", "Invalid request."),
            "type": error.get("type", "validation_error"),
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Request validation failed.",
            "errors": errors,
            "path": request.url.path,
        },
    )


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        debug=settings.app_debug,
        lifespan=lifespan,
    )
    application.add_exception_handler(
        RequestValidationError,
        request_validation_exception_handler,
    )
    application.add_middleware(
        RequestValidationMiddleware,
        api_prefix=settings.api_v1_prefix,
        validate_requests=settings.api_validate_requests,
        enforce_json_content_type=settings.api_enforce_json_content_type,
        max_request_body_bytes=settings.api_max_request_body_bytes,
    )
    application.add_middleware(
        AuthenticationMiddleware,
        api_prefix=settings.api_v1_prefix,
    )
    application.add_middleware(
        HTTPSMiddleware,
        enforce_https=settings.https_enforced,
        redirect_status_code=settings.https_redirect_status_code,
        hsts_enabled=settings.https_hsts_enabled,
        hsts_max_age=settings.https_hsts_max_age,
        hsts_include_subdomains=settings.https_hsts_include_subdomains,
        hsts_preload=settings.https_hsts_preload,
    )
    application.include_router(health_router)
    application.include_router(api_router, prefix=settings.api_v1_prefix)
    return application


app = create_app()
