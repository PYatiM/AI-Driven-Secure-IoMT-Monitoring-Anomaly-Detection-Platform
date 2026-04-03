from __future__ import annotations

import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from backend.app.db.session import get_session_factory
from backend.app.services.audit import AuditContext, write_audit_log

logger = logging.getLogger(__name__)


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        api_prefix: str = "/api/v1",
        enabled: bool = True,
    ) -> None:
        super().__init__(app)
        self.api_prefix = api_prefix.rstrip("/")
        self.enabled = enabled

    async def dispatch(self, request: Request, call_next) -> Response:
        if getattr(request.state, "audit_context", None) is None:
            request.state.audit_context = AuditContext()

        if not self.enabled or not self._should_log(request):
            return await call_next(request)

        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            db = get_session_factory()()
            try:
                write_audit_log(db, request, status_code)
            except Exception:
                db.rollback()
                logger.exception(
                    "Failed to persist audit log for %s %s",
                    request.method,
                    request.url.path,
                )
            finally:
                db.close()

    def _should_log(self, request: Request) -> bool:
        path = request.url.path
        if request.method == "OPTIONS":
            return False
        return path == self.api_prefix or path.startswith(f"{self.api_prefix}/")
