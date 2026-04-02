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

try:
    from shared.cache import close_cache, get_cache
except ImportError:
    try:
        from packages.shared.cache import close_cache, get_cache
    except ImportError:
        class _NoOpCache:
            """Safe fallback when the shared cache package is unavailable."""

            async def get(self, key: str) -> Any:
                return None

            async def set(self, key: str, value: Any, ttl: int = 60) -> None:
                pass

            async def delete(self, key: str) -> None:
                pass

            async def exists(self, key: str) -> bool:
                return False

            async def incr(self, key: str, ttl: int = 60) -> int:
                return 1

            async def close(self) -> None:
                pass

        _CACHE_FALLBACK = _NoOpCache()

        def get_cache():
            return _CACHE_FALLBACK

        async def close_cache() -> None:
            await _CACHE_FALLBACK.close()


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

# Fallback values used when the DB has no real data yet (demo mode)
DEMO_TOTAL_FARMS = 142
DEMO_SENSORS_PER_PRODUCT = 3
DEMO_ACTIVE_SENSORS = 450
DEMO_ACTIVE_CYCLES = 25
DEMO_COMPLETED_CYCLES = 102


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_latest_status_per_product(product: models.Product) -> str | None:
    if not product.tracking_history:
        return None
    return max(product.tracking_history, key=lambda event: event.timestamp).status


def _build_status_distribution(products: list[models.Product]) -> dict:
    distribution = {}
    for product in products:
        latest_status = _get_latest_status_per_product(product)
        if latest_status:
            distribution[latest_status] = distribution.get(latest_status, 0) + 1
    return distribution


def _build_origin_distribution(products: list[models.Product]) -> dict:
    distribution = {}
    for product in products:
        origin = product.origin or "Unknown"
        distribution[origin] = distribution.get(origin, 0) + 1
    return distribution


def _format_tracking_event_as_activity(event: models.TrackingEvent) -> dict:
    return {
        "timestamp": event.timestamp.isoformat() + "Z",
        "event": f"Product {event.product_id[:8]} status changed to {event.status} at {event.location}",
    }


@app.get("/")
def read_root():
    return {"message": "Welcome to AgriGuard API (DB Connected)", "status": "running"}


@app.get("/api/v1/dashboard/summary", response_model=schemas.DashboardResponse)
async def get_frontend_dashboard_summary(db: Session = Depends(get_db)):
    # Redis cache — 30s TTL (500 concurrent users → 1 DB hit per 30s)
    cache = get_cache()
    cached = await cache.get("agriguard:dashboard:frontend")
    if cached is not None:
        return cached

    farmer_count = db.query(models.User).filter(models.User.role == "Farmer").count()
    total_products = db.query(models.Product).count()
    harvested_products = db.query(models.Product).filter(models.Product.harvest_date != None).count()  # noqa: E711 — SQLAlchemy requires != None for IS NOT NULL
    active_cycles = total_products - harvested_products

    recent_events = db.query(models.TrackingEvent).order_by(models.TrackingEvent.timestamp.desc()).limit(5).all()
    recent_activity = [_format_tracking_event_as_activity(e) for e in recent_events]

    if not recent_activity:
        recent_activity = [
            {"timestamp": datetime.now(UTC).isoformat() + "Z", "event": "System initialized. Waiting for sensor data."}
        ]

    has_real_data = total_products > 0
    result = {
        "status": "success",
        "data": {
            "total_farms": farmer_count if has_real_data else DEMO_TOTAL_FARMS,
            "active_sensors": total_products * DEMO_SENSORS_PER_PRODUCT if has_real_data else DEMO_ACTIVE_SENSORS,
            "critical_alerts": 0,
            "growth_cycles": {
                "active": active_cycles if has_real_data else DEMO_ACTIVE_CYCLES,
                "completed": harvested_products if has_real_data else DEMO_COMPLETED_CYCLES,
            },
            "recent_activity": recent_activity,
        },
    }
    await cache.set("agriguard:dashboard:frontend", result, ttl=30)
    return result


@app.get("/dashboard/summary")
async def get_supply_chain_summary(db: Session = Depends(get_db)):
    # Redis cache — 30s TTL
    cache = get_cache()
    cached = await cache.get("agriguard:dashboard:supply_chain")
    if cached is not None:
        return cached

    # Eager-load relationships to avoid N+1 queries (28,400 → 3 at 100x scale)
    products = (
        db.query(models.Product)
        .options(
            selectinload(models.Product.certificates),
            selectinload(models.Product.tracking_history),
        )
        .all()
    )

    certified_count = sum(1 for p in products if p.certificates)
    cold_chain_count = sum(1 for p in products if p.requires_cold_chain)
    total_tracking_events = sum(len(p.tracking_history) for p in products)

    result = {
        "total_products": len(products),
        "certified_products": certified_count,
        "cold_chain_products": cold_chain_count,
        "total_tracking_events": total_tracking_events,
        "status_distribution": _build_status_distribution(products),
        "origin_distribution": _build_origin_distribution(products),
    }
    await cache.set("agriguard:dashboard:supply_chain", result, ttl=30)
    return result


@app.post("/users/", response_model=schemas.User)
def create_user(
    user: schemas.UserCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)
):
    db_user = models.User(
        id=str(uuid.uuid4()),
        created_at=datetime.now(UTC),
        role=user.role,
        name=user.name,
        organization=user.organization,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@app.post("/products/", response_model=schemas.Product)
def create_product(
    product: schemas.ProductCreate,
    owner_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    product_id = str(uuid.uuid4())
    get_chain().log_event(product_id, {"action": "REGISTER", "owner": owner_id})

    db_product = models.Product(
        id=product_id,
        owner_id=owner_id,
        qr_code=f"agri://verify/{product_id}",
        name=product.name,
        description=product.description,
        category=product.category,
        origin=product.origin,
        harvest_date=product.harvest_date,
        requires_cold_chain=product.requires_cold_chain,
    )
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product


@app.get("/products/", response_model=list[schemas.Product])
def list_products(db: Session = Depends(get_db)):
    return db.query(models.Product).all()


@app.get("/products/{product_id}", response_model=schemas.Product)
def get_product(product_id: str, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@app.get("/products/{product_id}/history")
def get_product_history(product_id: str, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    history = get_chain().get_product_history(product_id)
    return {"product_id": product_id, "history": history}


@app.post("/products/{product_id}/certifications", response_model=schemas.Product)
def add_certification(
    product_id: str,
    cert_type: str,
    issued_by: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    try:
        cert_id = f"CERT-{uuid.uuid4().hex[:8].upper()}"
        new_cert = models.Certificate(
            cert_id=cert_id,
            product_id=product_id,
            issued_by=issued_by,
            issue_date=datetime.now(UTC),
            cert_type=cert_type,
        )
        db.add(new_cert)
        get_chain().log_event(
            product_id,
            {
                "action": "CERTIFICATION_ISSUED",
                "cert_id": cert_id,
                "cert_type": cert_type,
                "issued_by": issued_by,
            },
        )
        db.commit()
        db.refresh(product)
        return product
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Certification failed: {str(e)}") from e


@app.post("/products/{product_id}/track")
def add_tracking_event(
    product_id: str,
    status: str,
    location: str,
    handler_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    try:
        event = models.TrackingEvent(
            product_id=product_id,
            timestamp=datetime.now(UTC),
            status=status,
            location=location,
            handler_id=handler_id,
        )
        db.add(event)
        get_chain().log_event(
            product_id,
            {
                "timestamp": event.timestamp.isoformat(),
                "status": status,
                "location": location,
                "handler_id": handler_id,
            },
        )
        db.commit()
        db.refresh(event)
        return {"status": "success", "event": {"id": event.id, "status": event.status, "location": event.location}}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Tracking event failed: {str(e)}") from e


@app.post("/qr-events", response_model=schemas.QRScanEventResponse)
def capture_qr_scan_event(payload: schemas.QRScanEventCreate, db: Session = Depends(get_db)):
    try:
        event = models.QRScanEvent(
            session_id=payload.session_id,
            event_type=payload.event_type,
            occurred_at=payload.occurred_at or datetime.now(UTC),
            product_id=payload.product_id,
            qr_value=payload.qr_value,
            error_code=payload.error_code,
            error_message=payload.error_message,
            recovery_method=payload.recovery_method,
            source=payload.source,
            variant_id=payload.variant_id,
            metadata_json=json.dumps(payload.event_payload, ensure_ascii=False),
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        # Business metrics
        try:
            from shared.business_metrics import biz

            biz.qr_scan(payload.event_type)
            if payload.event_type == "verification_complete":
                biz.verification_complete()
        except ImportError:
            pass
        return {"status": "success", "event_id": event.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"QR event capture failed: {str(e)}") from e


@app.get("/qr-events/summary")
def get_qr_event_summary(hours: int = 24, variant_id: str | None = None, db: Session = Depends(get_db)):
    since = datetime.now(UTC) - timedelta(hours=hours)
    query = db.query(models.QRScanEvent).filter(models.QRScanEvent.occurred_at >= since)
    if variant_id:
        query = query.filter(models.QRScanEvent.variant_id == variant_id)

    events = query.order_by(models.QRScanEvent.occurred_at.asc()).all()
    if not events:
        return {
            "hours": hours,
            "variant_id": variant_id or "all",
            "since": since.isoformat() + "Z",
            "total_events": 0,
            "total_sessions": 0,
            "event_counts": {},
            "error_counts": {},
            "variant_counts": {},
            "funnel": {
                "scan_start_sessions": 0,
                "scan_failure_sessions": 0,
                "scan_recovery_sessions": 0,
                "verification_complete_sessions": 0,
                "verification_completion_rate": 0.0,
                "recovery_rate_after_failure": 0.0,
            },
        }

    event_counts: dict[str, int] = {}
    error_counts: dict[str, int] = {}
    variant_counts: dict[str, int] = {}
    sessions: dict[str, set[str]] = {}

    for event in events:
        event_counts[event.event_type] = event_counts.get(event.event_type, 0) + 1
        variant_counts[event.variant_id] = variant_counts.get(event.variant_id, 0) + 1
        sessions.setdefault(event.session_id, set()).add(event.event_type)
        if event.error_code:
            error_counts[event.error_code] = error_counts.get(event.error_code, 0) + 1

    total_sessions = len(sessions)
    scan_start_sessions = sum(1 for value in sessions.values() if "scan_start" in value)
    scan_failure_sessions = sum(1 for value in sessions.values() if "scan_failure" in value)
    scan_recovery_sessions = sum(1 for value in sessions.values() if "scan_recovery" in value)
    verification_complete_sessions = sum(1 for value in sessions.values() if "verification_complete" in value)

    completion_rate = round(verification_complete_sessions / scan_start_sessions, 4) if scan_start_sessions else 0.0
    recovery_rate = round(scan_recovery_sessions / scan_failure_sessions, 4) if scan_failure_sessions else 0.0

    return {
        "hours": hours,
        "variant_id": variant_id or "all",
        "since": since.isoformat() + "Z",
        "total_events": len(events),
        "total_sessions": total_sessions,
        "event_counts": event_counts,
        "error_counts": error_counts,
        "variant_counts": variant_counts,
        "funnel": {
            "scan_start_sessions": scan_start_sessions,
            "scan_failure_sessions": scan_failure_sessions,
            "scan_recovery_sessions": scan_recovery_sessions,
            "verification_complete_sessions": verification_complete_sessions,
            "verification_completion_rate": completion_rate,
            "recovery_rate_after_failure": recovery_rate,
        },
    }


# ============== IoT Cold-Chain ==============


@app.get("/iot/status")
async def iot_status():
    """현재 IoT 센서 상태 집계"""
    return get_current_status()


@app.get("/iot/readings")
async def iot_readings(hours: int = 24):
    """최근 N시간 센서 데이터"""
    return get_latest_readings(hours)


@app.websocket("/ws/iot")
async def ws_iot(websocket: WebSocket):
    """실시간 IoT WebSocket 피드"""
    await handle_ws_connection(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)
