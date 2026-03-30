"""
shared.audit — API audit logging middleware for FastAPI services.

Records every HTTP request with caller identity, method, path, status,
duration, and client IP.  Logs are emitted via structlog (JSON for Loki)
when available, otherwise stdlib logging.

Usage::
    from shared.audit import setup_audit_log
    setup_audit_log(app, service_name="agriguard")
"""
from __future__ import annotations

import time
from typing import Any

try:
    import structlog
    _log = structlog.get_logger("audit")
    _STRUCTLOG = True
except ImportError:
    import logging
    _log = logging.getLogger("audit")
    _STRUCTLOG = False


def setup_audit_log(app: Any, *, service_name: str = "app") -> None:
    """Attach audit-logging middleware to a FastAPI/Starlette app."""
    from starlette.requests import Request

    @app.middleware("http")
    async def audit_middleware(request: Request, call_next):
        start = time.perf_counter()
        client_ip = request.client.host if request.client else "unknown"
        user_id = (
            request.headers.get("x-user-id")
            or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            or client_ip
        )
        method = request.method
        path = request.url.path

        # Skip noisy endpoints
        if path in ("/metrics", "/health", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            status = response.status_code

            _log.info(
                "api_request",
                service=service_name,
                user_id=user_id,
                method=method,
                path=path,
                status=status,
                duration_ms=duration_ms,
                client_ip=client_ip,
            )
            return response
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            _log.error(
                "api_request_error",
                service=service_name,
                user_id=user_id,
                method=method,
                path=path,
                status=500,
                duration_ms=duration_ms,
                client_ip=client_ip,
                error=str(exc),
            )
            raise
