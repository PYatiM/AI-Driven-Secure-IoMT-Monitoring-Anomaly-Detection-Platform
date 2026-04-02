from __future__ import annotations

import logging
from typing import Literal

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from backend.app.api.deps import (
    AuthenticationError,
    authenticate_device_api_key,
    authenticate_user_bearer_token,
)
from backend.app.db.session import get_session_factory

logger = logging.getLogger(__name__)
AuthMode = Literal["user", "device"]


class AuthenticationMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, api_prefix: str = "/api/v1") -> None:
        super().__init__(app)
        normalized_prefix = api_prefix.rstrip("/")
        self.api_prefix = normalized_prefix
        self.public_paths = {
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            f"{normalized_prefix}/auth/register",
            f"{normalized_prefix}/auth/login",
        }
        self.user_exact_paths = {
            f"{normalized_prefix}/auth/me",
            f"{normalized_prefix}/devices/register",
        }
        self.user_prefixes = (f"{normalized_prefix}/users",)
        self.device_exact_paths = {f"{normalized_prefix}/devices/me"}
        self.device_prefixes = (
            f"{normalized_prefix}/alerts",
            f"{normalized_prefix}/telemetry",
        )

    async def dispatch(self, request: Request, call_next) -> Response:
        request.state.current_user = None
        request.state.current_device = None

        if request.method == "OPTIONS" or request.url.path in self.public_paths:
            return await call_next(request)

        auth_mode = self._resolve_auth_mode(request.url.path)
        if auth_mode is None:
            return await call_next(request)

        db = get_session_factory()()
        try:
            if auth_mode == "user":
                request.state.current_user = authenticate_user_bearer_token(
                    db,
                    request.headers.get("Authorization"),
                )
            else:
                request.state.current_device = authenticate_device_api_key(
                    db,
                    request.headers.get("X-API-Key"),
                )
        except AuthenticationError as error:
            return JSONResponse(
                status_code=error.status_code,
                content={"detail": error.detail},
                headers=error.headers or {},
            )
        except Exception:
            logger.exception(
                "Authentication middleware failed for %s",
                request.url.path,
            )
            return JSONResponse(
                status_code=500,
                content={"detail": "Authentication middleware failed."},
            )
        finally:
            db.close()

        return await call_next(request)

    def _resolve_auth_mode(self, path: str) -> AuthMode | None:
        if path in self.user_exact_paths or self._matches_prefix(path, self.user_prefixes):
            return "user"
        if path in self.device_exact_paths or self._matches_prefix(
            path,
            self.device_prefixes,
        ):
            return "device"
        return None

    @staticmethod
    def _matches_prefix(path: str, prefixes: tuple[str, ...]) -> bool:
        return any(path == prefix or path.startswith(f"{prefix}/") for prefix in prefixes)
