from __future__ import annotations

import json

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response


class RequestValidationMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        api_prefix: str = "/api/v1",
        validate_requests: bool = True,
        enforce_json_content_type: bool = True,
        max_request_body_bytes: int = 1048576,
    ) -> None:
        super().__init__(app)
        self.api_prefix = api_prefix.rstrip("/")
        self.validate_requests = validate_requests
        self.enforce_json_content_type = enforce_json_content_type
        self.max_request_body_bytes = max_request_body_bytes
        self.body_methods = {"POST", "PUT", "PATCH"}

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self.validate_requests or not self._is_api_request(request.url.path):
            return await call_next(request)

        if request.method not in self.body_methods:
            return await call_next(request)

        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length header."},
                )

            if declared_length > self.max_request_body_bytes:
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": "Request body is too large.",
                        "max_request_body_bytes": self.max_request_body_bytes,
                    },
                )

        body = await request.body()
        if not body:
            return await call_next(request)

        if len(body) > self.max_request_body_bytes:
            return JSONResponse(
                status_code=413,
                content={
                    "detail": "Request body is too large.",
                    "max_request_body_bytes": self.max_request_body_bytes,
                },
            )

        if self.enforce_json_content_type and not self._is_json_content_type(
            request.headers.get("content-type")
        ):
            return JSONResponse(
                status_code=415,
                content={
                    "detail": "Content-Type must be application/json for this endpoint.",
                },
            )

        try:
            json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JSONResponse(
                status_code=400,
                content={"detail": "Malformed JSON request body."},
            )

        return await call_next(request)

    def _is_api_request(self, path: str) -> bool:
        return path == self.api_prefix or path.startswith(f"{self.api_prefix}/")

    @staticmethod
    def _is_json_content_type(content_type: str | None) -> bool:
        if not content_type:
            return False
        normalized = content_type.split(";", 1)[0].strip().lower()
        return normalized == "application/json" or normalized.endswith("+json")
