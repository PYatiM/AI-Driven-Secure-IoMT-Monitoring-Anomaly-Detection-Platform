from __future__ import annotations

import time

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware

REQUEST_COUNT = Counter(
    "backend_http_requests_total",
    "Total HTTP requests handled by the backend application.",
    ["method", "path", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "backend_http_request_duration_seconds",
    "Latency of backend HTTP requests in seconds.",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0),
)

metrics_router = APIRouter(tags=["metrics"])


@metrics_router.get("/metrics", include_in_schema=False)
def prometheus_metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    @staticmethod
    def _resolve_metric_path(request) -> str:
        route = request.scope.get("route")
        route_path = getattr(route, "path", None)
        if isinstance(route_path, str) and route_path:
            return route_path
        return request.url.path

    async def dispatch(self, request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        duration = max(0.0, time.perf_counter() - started)

        method = request.method
        path = self._resolve_metric_path(request)
        status_code = str(response.status_code)

        REQUEST_COUNT.labels(method=method, path=path, status_code=status_code).inc()
        REQUEST_LATENCY.labels(method=method, path=path).observe(duration)
        return response
