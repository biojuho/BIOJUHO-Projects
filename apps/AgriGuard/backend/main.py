import asyncio
import json
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import models
import schemas
from auth import get_current_user
from database import SessionLocal, initialize_database, verify_database_connection
from fastapi import Depends, FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from iot_service import batch_flush_loop, get_current_status, get_latest_readings, handle_ws_connection, redis_subscriber_loop, sensor_simulation_loop
from services.chain_simulator import get_chain
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload
from starlette.middleware.sessions import SessionMiddleware

# ── Observability (Logfire) ─────────────────────────────────
_WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(_WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE_ROOT))

try:
    from shared.observability import setup_observability

    _LOGFIRE_OK = True
except ImportError:
    import logging as _logging
    _logging.getLogger(__name__).warning(
        "shared.observability를 찾을 수 없습니다 — Logfire 비활성 (WORKSPACE_ROOT=%s)", _WORKSPACE_ROOT
    )
    _LOGFIRE_OK = False

try:
    from shared.metrics import setup_metrics

    _METRICS_OK = True
except ImportError:
    try:
        from packages.shared.metrics import setup_metrics

        _METRICS_OK = True
    except ImportError:
        _METRICS_OK = False

from dependencies import close_cache, get_cache


@asynccontextmanager
async def lifespan(app):
    initialize_database()
    verify_database_connection()

    # Start IoT simulation
    sim_task = asyncio.create_task(sensor_simulation_loop())

    # Start IoT batch flush worker (100x scale: reduces DB commits by ~200x)
    flush_task = asyncio.create_task(batch_flush_loop())

    # Start Redis Pub/Sub subscriber (multi-worker WS broadcasting)
    pubsub_task = asyncio.create_task(redis_subscriber_loop())

    # Start MQTT if broker is configured
    mqtt_host = os.environ.get("MQTT_BROKER_HOST", "")
    mqtt_task = None
    if mqtt_host:
        from iot_service import add_reading_from_mqtt
        from mqtt_service import MQTTSensorService

        mqtt_service = MQTTSensorService(
            broker_host=mqtt_host,
            broker_port=int(os.environ.get("MQTT_BROKER_PORT", "1883")),
            on_reading=add_reading_from_mqtt,
        )
        mqtt_task = asyncio.create_task(mqtt_service.start())

    yield

    sim_task.cancel()
    flush_task.cancel()
    pubsub_task.cancel()
    await close_cache()
    if mqtt_task:
        mqtt_task.cancel()


app = FastAPI(title="AgriGuard API", version="0.2.0", lifespan=lifespan)

ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
_SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not _SECRET_KEY:
    import warnings  # noqa: E402
    warnings.warn(
        "SECRET_KEY is not set! Using an insecure default. "
        "Set SECRET_KEY environment variable for production.",
        stacklevel=1,
    )
    _SECRET_KEY = "INSECURE-DEV-ONLY-" + os.urandom(16).hex()

app.add_middleware(
    SessionMiddleware,
    secret_key=_SECRET_KEY,
)

# ── Admin Panel (/admin) ────────────────────────────────────
from admin import setup_admin

setup_admin(app)

# ── Logfire Observability ───────────────────────────────────
if _LOGFIRE_OK:
    setup_observability(
        app,
        service_name="agriguard",
    )

# ── Prometheus Metrics (/metrics) ──────────────────────────
if _METRICS_OK:
    setup_metrics(app, service_name="agriguard")

# ── Structured Logging (JSON for Loki) ─────────────────────
try:
    from shared.structured_logging import setup_logging as setup_structured_logging

    setup_structured_logging(service_name="agriguard")
except ImportError:
    pass

# ── Audit Log ──────────────────────────────────────────────
try:
    from shared.audit import setup_audit_log

    setup_audit_log(app, service_name="agriguard")
except ImportError:
    pass

# ── Rate Limiting (100x scale) ─────────────────────────────
_RATE_LIMIT_MAX = int(os.environ.get("RATE_LIMIT_MAX", "100"))  # per minute
_RATE_LIMIT_WINDOW = 60  # seconds


@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    """Redis-backed rate limiter: 100 req/min per IP."""
    # Skip rate limiting for WebSocket upgrades and health checks
    if request.url.path in ("/health", "/ws/iot", "/metrics"):
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    cache = get_cache()
    key = f"ratelimit:{client_ip}:{int(time.time()) // _RATE_LIMIT_WINDOW}"
    count = await cache.incr(key, ttl=_RATE_LIMIT_WINDOW)

    if count > _RATE_LIMIT_MAX:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please try again later."},
            headers={"Retry-After": str(_RATE_LIMIT_WINDOW)},
        )

    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(_RATE_LIMIT_MAX)
    response.headers["X-RateLimit-Remaining"] = str(max(0, _RATE_LIMIT_MAX - count))
    return response

from routers import dashboard, users, products, qr_events, iot

app.include_router(dashboard.router, tags=["Dashboard"])
app.include_router(users.router, tags=["Users"])
app.include_router(products.router, tags=["Products"])
app.include_router(qr_events.router, tags=["QR Events"])
app.include_router(iot.router, tags=["IoT"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)
