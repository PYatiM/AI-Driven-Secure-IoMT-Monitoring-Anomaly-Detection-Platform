import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.app.api.router import api_router
from backend.app.api.routes.health import router as health_router
from backend.app.core.config import get_settings
from backend.app.core.logging import configure_logging
from backend.app.core.metrics import PrometheusMetricsMiddleware, metrics_router
from backend.app.middleware import (
    AuditLoggingMiddleware,
    AuthenticationMiddleware,
    FirewallMiddleware,
    HTTPSMiddleware,
    RequestValidationMiddleware,
)
from backend.app.security.key_storage import get_key_storage_status
from backend.app.services.telemetry_stream import get_telemetry_stream_service

settings = get_settings()
configure_logging(settings.log_level)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    key_storage_status = get_key_storage_status()
    telemetry_stream_service = get_telemetry_stream_service()
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
    logger.info("Firewall enabled: %s", settings.firewall_enabled)
    if settings.firewall_enabled:
        logger.info("Firewall mode: %s", settings.firewall_mode)
        logger.info("Firewall config path: %s", settings.firewall_config_path)
        logger.info("Firewall default action: %s", settings.firewall_default_action)
    logger.info("API request validation enabled: %s", settings.api_validate_requests)
    logger.info("Telemetry queue enabled: %s", settings.telemetry_queue_enabled)
    if settings.telemetry_queue_enabled:
        logger.info(
            "Telemetry queue batch size: %s (flush interval: %sms)",
            settings.telemetry_queue_batch_size,
            settings.telemetry_queue_flush_interval_ms,
        )
        await telemetry_stream_service.start(
            batch_size=settings.telemetry_queue_batch_size,
            flush_interval_seconds=settings.telemetry_queue_flush_interval_ms / 1000.0,
        )
    logger.info("Audit logging enabled: %s", settings.audit_logging_enabled)
    logger.info("Security event logging enabled: %s", settings.security_event_logging_enabled)
    logger.info("Alert escalation enabled: %s", settings.alert_escalation_enabled)
    if settings.alert_escalation_enabled:
        logger.info("Alert escalation target: %s", settings.alert_escalation_target)
    logger.info("Secure key storage enabled: %s", key_storage_status.enabled)
    if key_storage_status.enabled:
        logger.info("Secure key storage configured: %s", key_storage_status.configured)
        logger.info("Secure key storage path: %s", key_storage_status.path)
        logger.info(
            "Secure key storage env fallback enabled: %s",
            key_storage_status.env_fallback_enabled,
        )
    yield
    if settings.telemetry_queue_enabled:
        await telemetry_stream_service.stop()
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
    application.add_middleware(PrometheusMetricsMiddleware)
    application.add_middleware(
        AuthenticationMiddleware,
        api_prefix=settings.api_v1_prefix,
    )
    application.add_middleware(
        FirewallMiddleware,
        enabled=settings.firewall_enabled,
        mode=settings.firewall_mode,
        config_path=settings.firewall_config_path,
        default_action=settings.firewall_default_action,
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
    application.add_middleware(
        AuditLoggingMiddleware,
        api_prefix=settings.api_v1_prefix,
        enabled=settings.audit_logging_enabled,
    )
    application.include_router(health_router)
    application.include_router(metrics_router)
    application.include_router(api_router, prefix=settings.api_v1_prefix)
    return application


app = create_app()
