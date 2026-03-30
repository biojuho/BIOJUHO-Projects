"""
shared.metrics — Prometheus metrics middleware for FastAPI services.

Exposes a /metrics endpoint and tracks request count, latency, and
in-flight requests per service.  Falls back to no-op when
prometheus_client is not installed.

Usage::
    from shared.metrics import setup_metrics

    setup_metrics(app, service_name="agriguard")
"""

from __future__ import annotations

import time
from typing import Any

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )

    _PROM_AVAILABLE = True
except ImportError:
    _PROM_AVAILABLE = False


def _normalize_request_path(request: Any) -> str:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    if route_path:
        return route_path
    return request.url.path


def setup_metrics(app: Any, *, service_name: str = "app") -> None:
    """Instrument a FastAPI app with Prometheus metrics.

    Safe to call even when prometheus_client is not installed — the app
    will work normally without metrics.
    """
    if not _PROM_AVAILABLE:
        return

    registry = CollectorRegistry()

    request_count = Counter(
        "http_requests_total",
        "Total HTTP requests",
        ["service", "method", "path", "status"],
        registry=registry,
    )
    request_latency = Histogram(
        "http_request_duration_seconds",
        "HTTP request latency in seconds",
        ["service", "method", "path"],
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
        registry=registry,
    )
    in_flight = Gauge(
        "http_requests_in_flight",
        "Number of in-flight HTTP requests",
        ["service"],
        registry=registry,
    )

    from starlette.requests import Request
    from starlette.responses import Response

    @app.middleware("http")
    async def prometheus_middleware(request: Request, call_next):
        raw_path = request.url.path
        if raw_path == "/metrics":
            return await call_next(request)

        path = _normalize_request_path(request)
        method = request.method

        in_flight.labels(service=service_name).inc()
        start = time.perf_counter()
        try:
            response = await call_next(request)
            elapsed = time.perf_counter() - start
            status = str(response.status_code)
            request_count.labels(service=service_name, method=method, path=path, status=status).inc()
            request_latency.labels(service=service_name, method=method, path=path).observe(elapsed)
            return response
        except Exception:
            elapsed = time.perf_counter() - start
            request_count.labels(service=service_name, method=method, path=path, status="500").inc()
            request_latency.labels(service=service_name, method=method, path=path).observe(elapsed)
            raise
        finally:
            in_flight.labels(service=service_name).dec()

    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint():
        return Response(
            content=generate_latest(registry),
            media_type=CONTENT_TYPE_LATEST,
        )
