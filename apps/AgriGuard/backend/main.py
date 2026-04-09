import asyncio
import logging
import os
import sys
import time
import warnings
from contextlib import asynccontextmanager
from pathlib import Path

from database import initialize_database, verify_database_connection
from dependencies import close_cache, get_cache
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from iot_service import (
    add_reading_from_mqtt,
    batch_flush_loop,
    close_iot_resources,
    redis_subscriber_loop,
    sensor_simulation_loop,
)
from starlette.middleware.sessions import SessionMiddleware

logger = logging.getLogger(__name__)

_WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(_WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE_ROOT))

try:
    from shared.observability import setup_observability

    _LOGFIRE_OK = True
except ImportError:
    logger.warning("shared.observability not available; Logfire disabled (WORKSPACE_ROOT=%s)", _WORKSPACE_ROOT)
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


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class _IngestLeaderLock:
    def __init__(self, path: Path):
        self.path = path
        self._handle = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        handle.seek(0)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
            handle.seek(0)

        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False

        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()).encode("ascii"))
        handle.flush()
        handle.seek(0)
        self._handle = handle
        return True

    def release(self) -> None:
        if self._handle is None:
            return

        try:
            self._handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            logger.debug("Failed to release IoT ingest lock cleanly", exc_info=True)
        finally:
            self._handle.close()
            self._handle = None


def _get_ingest_lock_path() -> Path:
    configured = os.environ.get("IOT_INGEST_LOCK_PATH", "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().with_name(".iot-ingest.lock")


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    verify_database_connection()

    background_tasks: list[asyncio.Task] = []
    ingest_lock: _IngestLeaderLock | None = None
    mqtt_service = None

    simulation_enabled = _env_flag("IOT_SIMULATION_ENABLED", default=False)
    mqtt_host = os.environ.get("MQTT_BROKER_HOST", "").strip()
    mqtt_enabled = bool(mqtt_host) and _env_flag("IOT_MQTT_ENABLED", default=True)

    try:
        background_tasks.append(asyncio.create_task(redis_subscriber_loop()))

        if simulation_enabled or mqtt_enabled:
            ingest_lock = _IngestLeaderLock(_get_ingest_lock_path())
            if ingest_lock.acquire():
                background_tasks.append(asyncio.create_task(batch_flush_loop()))

                if simulation_enabled:
                    background_tasks.append(asyncio.create_task(sensor_simulation_loop()))

                if mqtt_enabled:
                    from mqtt_service import MQTTSensorService

                    mqtt_service = MQTTSensorService(
                        broker_host=mqtt_host,
                        broker_port=int(os.environ.get("MQTT_BROKER_PORT", "1883")),
                        on_reading=add_reading_from_mqtt,
                    )
                    background_tasks.append(asyncio.create_task(mqtt_service.start()))

                logger.info(
                    "IoT ingest leader active: simulation=%s mqtt=%s lock=%s",
                    simulation_enabled,
                    mqtt_enabled,
                    ingest_lock.path,
                )
            else:
                logger.info(
                    "Skipping IoT ingest on this worker because another process holds %s",
                    ingest_lock.path,
                )
        else:
            logger.info("IoT ingest disabled: simulation=%s mqtt=%s", simulation_enabled, mqtt_enabled)

        yield
    finally:
        if mqtt_service is not None:
            await mqtt_service.stop()

        for task in background_tasks:
            task.cancel()
        if background_tasks:
            await asyncio.gather(*background_tasks, return_exceptions=True)

        await close_iot_resources()
        await close_cache()

        if ingest_lock is not None:
            ingest_lock.release()


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
    warnings.warn(
        "SECRET_KEY is not set! Using an insecure default. Set SECRET_KEY environment variable for production.",
        stacklevel=1,
    )
    _SECRET_KEY = "INSECURE-DEV-ONLY-" + os.urandom(16).hex()

app.add_middleware(SessionMiddleware, secret_key=_SECRET_KEY)

from admin import setup_admin

setup_admin(app)

if _LOGFIRE_OK:
    setup_observability(app, service_name="agriguard")

if _METRICS_OK:
    setup_metrics(app, service_name="agriguard")

try:
    from shared.structured_logging import setup_logging as setup_structured_logging

    setup_structured_logging(service_name="agriguard")
except ImportError:
    pass

try:
    from shared.audit import setup_audit_log

    setup_audit_log(app, service_name="agriguard")
except ImportError:
    pass

_RATE_LIMIT_MAX = int(os.environ.get("RATE_LIMIT_MAX", "100"))
_RATE_LIMIT_WINDOW = 60


@app.middleware("http")
async def rate_limit_middleware(request, call_next):
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


from routers import dashboard, iot, products, qr_events, users

app.include_router(dashboard.router, tags=["Dashboard"])
app.include_router(users.router, tags=["Users"])
app.include_router(products.router, tags=["Products"])
app.include_router(qr_events.router, tags=["QR Events"])
app.include_router(iot.router, tags=["IoT"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)
