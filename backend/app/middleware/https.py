from __future__ import annotations

from fastapi import Request
from starlette.datastructures import URL
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse, Response


class HTTPSMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        enforce_https: bool = False,
        redirect_status_code: int = 307,
        hsts_enabled: bool = True,
        hsts_max_age: int = 31536000,
        hsts_include_subdomains: bool = True,
        hsts_preload: bool = False,
    ) -> None:
        super().__init__(app)
        self.enforce_https = enforce_https
        self.redirect_status_code = redirect_status_code
        self.hsts_enabled = hsts_enabled
        self.hsts_header_value = self._build_hsts_header(
            max_age=hsts_max_age,
            include_subdomains=hsts_include_subdomains,
            preload=hsts_preload,
        )

    async def dispatch(self, request: Request, call_next) -> Response:
        is_secure = self._is_secure_request(request)
        if self.enforce_https and not is_secure:
            https_url = self._to_https_url(request)
            return RedirectResponse(
                url=str(https_url),
                status_code=self.redirect_status_code,
            )

        response = await call_next(request)
        if self.hsts_enabled and is_secure:
            response.headers.setdefault(
                "Strict-Transport-Security",
                self.hsts_header_value,
            )
        return response

    @staticmethod
    def _build_hsts_header(
        max_age: int,
        include_subdomains: bool,
        preload: bool,
    ) -> str:
        directives = [f"max-age={max_age}"]
        if include_subdomains:
            directives.append("includeSubDomains")
        if preload:
            directives.append("preload")
        return "; ".join(directives)

    @staticmethod
    def _is_secure_request(request: Request) -> bool:
        if request.url.scheme == "https":
            return True

        forwarded_proto = request.headers.get("x-forwarded-proto")
        if forwarded_proto:
            return forwarded_proto.split(",", 1)[0].strip().lower() == "https"

        forwarded = request.headers.get("forwarded")
        if forwarded:
            segments = forwarded.split(";")
            for segment in segments:
                key, separator, value = segment.partition("=")
                if separator and key.strip().lower() == "proto":
                    return value.strip().lower().strip('"') == "https"

        return False

    @staticmethod
    def _to_https_url(request: Request) -> URL:
        forwarded_host = request.headers.get("x-forwarded-host")
        host = forwarded_host.split(",", 1)[0].strip() if forwarded_host else None
        if host:
            return request.url.replace(scheme="https", netloc=host)
        return request.url.replace(scheme="https")
