import asyncio
import json
import logging
import os
import random
import time
import uuid
from collections import deque
from datetime import UTC, datetime, timedelta
from typing import Any

from database import SessionLocal
from fastapi import WebSocket
from models import SensorReading
from sqlalchemy import case, func

logger = logging.getLogger(__name__)

_MAX_HISTORY = 2000
_ALERT_THRESHOLDS = {
    "temp_min": -25.0,
    "temp_max": 8.0,
    "humidity_min": 30.0,
    "humidity_max": 85.0,
}

# Keep a small in-memory fallback only for temporary DB failures.
_sensor_history: list[dict] = []

_ws_clients: list[WebSocket] = []
_ws_lock = asyncio.Lock()
_WS_SEND_TIMEOUT_SEC = 1.0

_reading_buffer: deque[dict] = deque()
_BATCH_SIZE = 200
_FLUSH_INTERVAL_SEC = 2.0
_MAX_FLUSH_BATCHES_PER_CYCLE = 10
_BUFFER_WARNING_THRESHOLD = 5000
_BUFFER_WARNING_INTERVAL_SEC = 30.0
_last_buffer_warning_at = 0.0

_PUBSUB_CHANNEL = "iot:broadcast"
_WORKER_INSTANCE_ID = os.getenv("AGRIGUARD_WORKER_ID", uuid.uuid4().hex)
_redis_pubsub_available = False

try:
    import redis.asyncio as aioredis

    _REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    _redis_pubsub_available = True
except ImportError:
    aioredis = None  # type: ignore[assignment]
    _REDIS_URL = ""

_publish_conn = None
_publish_conn_lock = asyncio.Lock()


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _parse_timestamp(timestamp: str) -> datetime:
    normalized = timestamp.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def _format_timestamp(value: datetime) -> str:
    normalized = value
    if normalized.tzinfo is not None:
        normalized = normalized.astimezone(UTC).replace(tzinfo=None)
    return normalized.isoformat() + "Z"


def _build_alerts(temperature: float, humidity: float) -> list[str]:
    alerts: list[str] = []
    if temperature < _ALERT_THRESHOLDS["temp_min"]:
        alerts.append(f"Temperature too low: {temperature}C")
    elif temperature > _ALERT_THRESHOLDS["temp_max"]:
        alerts.append(f"Temperature too high: {temperature}C")
    if humidity < _ALERT_THRESHOLDS["humidity_min"]:
        alerts.append(f"Humidity too low: {humidity}%")
    elif humidity > _ALERT_THRESHOLDS["humidity_max"]:
        alerts.append(f"Humidity too high: {humidity}%")
    return alerts


def _with_alert_metadata(reading: dict) -> dict:
    alerts = _build_alerts(reading["temperature"], reading["humidity"])
    enriched = dict(reading)
    enriched["alerts"] = alerts
    enriched["status"] = "alert" if alerts else "normal"
    return enriched


def _remember_local_reading(reading: dict) -> None:
    _sensor_history.append(reading)
    if len(_sensor_history) > _MAX_HISTORY:
        del _sensor_history[:-_MAX_HISTORY]


def _serialize_sensor_reading(row: SensorReading) -> dict:
    reading = {
        "sensor_id": row.sensor_id,
        "timestamp": _format_timestamp(row.timestamp),
        "temperature": row.temperature,
        "humidity": row.humidity,
        "battery": row.battery,
        "zone": row.zone,
    }
    reading = _with_alert_metadata(reading)
    # Preserve the stored status when available.
    reading["status"] = row.status or reading["status"]
    return reading


def _generate_mock_reading() -> dict:
    now = datetime.now(UTC)
    base_temp = -18.0 + random.gauss(0, 1.5)
    base_humidity = 55.0 + random.gauss(0, 5)

    if random.random() < 0.05:
        base_temp += random.choice([-10, 15, 20])

    return _with_alert_metadata(
        {
            "sensor_id": f"SENSOR-{random.choice(['A1', 'A2', 'B1', 'B2', 'C1'])}",
            "timestamp": now.isoformat().replace("+00:00", "Z"),
            "temperature": round(max(-30, min(50, base_temp)), 1),
            "humidity": round(max(0, min(100, base_humidity)), 1),
            "battery": round(random.uniform(60, 100), 0),
            "zone": random.choice(
                [
                    "Cold Storage A",
                    "Cold Storage B",
                    "Transport Unit 1",
                    "Transport Unit 2",
                ]
            ),
        }
    )


def _buffer_reading(reading: dict) -> None:
    global _last_buffer_warning_at

    _reading_buffer.append(reading)
    backlog = len(_reading_buffer)
    if backlog >= _BUFFER_WARNING_THRESHOLD:
        now = time.monotonic()
        if now - _last_buffer_warning_at >= _BUFFER_WARNING_INTERVAL_SEC:
            logger.warning("IoT reading backlog reached %d items; flush throughput is lagging", backlog)
            _last_buffer_warning_at = now


def _flush_reading_buffer() -> int:
    if not _reading_buffer:
        return 0

    batch: list[dict] = []
    while _reading_buffer and len(batch) < _BATCH_SIZE:
        batch.append(_reading_buffer.popleft())

    if not batch:
        return 0

    db = SessionLocal()
    try:
        objects = [
            SensorReading(
                sensor_id=reading["sensor_id"],
                timestamp=_parse_timestamp(reading["timestamp"]),
                temperature=reading["temperature"],
                humidity=reading["humidity"],
                battery=reading["battery"],
                zone=reading["zone"],
                status=reading["status"],
            )
            for reading in batch
        ]
        db.bulk_save_objects(objects)
        db.commit()
        return len(objects)
    except Exception:
        db.rollback()
        logger.exception("Failed to flush %d sensor readings", len(batch))
        for reading in reversed(batch):
            _reading_buffer.appendleft(reading)
        return 0
    finally:
        db.close()


async def _flush_pending_readings(*, max_batches: int | None = None) -> int:
    if not _reading_buffer:
        return 0

    total_flushed = 0
    batches_flushed = 0
    loop = asyncio.get_running_loop()

    while _reading_buffer and (max_batches is None or batches_flushed < max_batches):
        count = await loop.run_in_executor(None, _flush_reading_buffer)
        if count <= 0:
            break
        total_flushed += count
        batches_flushed += 1

    return total_flushed


def _get_local_history(hours: int) -> list[dict]:
    cutoff = _utcnow_naive() - timedelta(hours=hours)
    history: list[dict] = []
    for reading in _sensor_history:
        try:
            if _parse_timestamp(reading["timestamp"]) > cutoff:
                history.append(dict(reading))
        except (KeyError, ValueError):
            continue
    return history


def get_latest_readings(hours: int = 24) -> list[dict]:
    cutoff = _utcnow_naive() - timedelta(hours=hours)
    db = SessionLocal()
    try:
        rows = (
            db.query(SensorReading)
            .filter(SensorReading.timestamp > cutoff)
            .order_by(SensorReading.timestamp.desc())
            .limit(_MAX_HISTORY)
            .all()
        )
        return [_serialize_sensor_reading(row) for row in reversed(rows)]
    except Exception:
        logger.exception("Falling back to local IoT history because DB query failed")
        return _get_local_history(hours)
    finally:
        db.close()


def _get_current_status_from_local_history() -> dict:
    recent = _get_local_history(hours=1)
    if not recent:
        return {"zones": [], "overall_status": "no_data"}

    zones: dict[str, dict[str, Any]] = {}
    for reading in recent:
        zone = reading["zone"]
        if zone not in zones:
            zones[zone] = {"temps": [], "humidities": [], "alerts": 0}
        zones[zone]["temps"].append(reading["temperature"])
        zones[zone]["humidities"].append(reading["humidity"])
        if reading["status"] == "alert":
            zones[zone]["alerts"] += 1

    result = []
    for zone_name, data in zones.items():
        result.append(
            {
                "zone": zone_name,
                "avg_temp": round(sum(data["temps"]) / len(data["temps"]), 1),
                "avg_humidity": round(sum(data["humidities"]) / len(data["humidities"]), 1),
                "min_temp": min(data["temps"]),
                "max_temp": max(data["temps"]),
                "alert_count": data["alerts"],
                "readings_count": len(data["temps"]),
            }
        )

    has_alerts = any(zone["alert_count"] > 0 for zone in result)
    return {
        "zones": result,
        "overall_status": "alert" if has_alerts else "normal",
        "total_readings": len(recent),
    }


def get_current_status() -> dict:
    cutoff = _utcnow_naive() - timedelta(hours=1)
    db = SessionLocal()
    try:
        rows = (
            db.query(
                SensorReading.zone.label("zone"),
                func.avg(SensorReading.temperature).label("avg_temp"),
                func.avg(SensorReading.humidity).label("avg_humidity"),
                func.min(SensorReading.temperature).label("min_temp"),
                func.max(SensorReading.temperature).label("max_temp"),
                func.sum(case((SensorReading.status == "alert", 1), else_=0)).label("alert_count"),
                func.count(SensorReading.id).label("readings_count"),
            )
            .filter(SensorReading.timestamp > cutoff)
            .group_by(SensorReading.zone)
            .all()
        )

        if not rows:
            return {"zones": [], "overall_status": "no_data"}

        zones = [
            {
                "zone": row.zone,
                "avg_temp": round(float(row.avg_temp), 1),
                "avg_humidity": round(float(row.avg_humidity), 1),
                "min_temp": float(row.min_temp),
                "max_temp": float(row.max_temp),
                "alert_count": int(row.alert_count or 0),
                "readings_count": int(row.readings_count),
            }
            for row in rows
        ]
        total_readings = sum(zone["readings_count"] for zone in zones)
        has_alerts = any(zone["alert_count"] > 0 for zone in zones)
        return {
            "zones": zones,
            "overall_status": "alert" if has_alerts else "normal",
            "total_readings": total_readings,
        }
    except Exception:
        logger.exception("Falling back to local IoT status because DB query failed")
        return _get_current_status_from_local_history()
    finally:
        db.close()


def _build_broadcast_message(reading: dict) -> dict:
    return {
        "broadcast_id": uuid.uuid4().hex,
        "origin": _WORKER_INSTANCE_ID,
        "reading": reading,
    }


def _decode_broadcast_message(payload: str | dict[str, Any]) -> dict:
    message = json.loads(payload) if isinstance(payload, str) else payload
    if isinstance(message, dict) and "reading" in message:
        return message
    return {
        "broadcast_id": uuid.uuid4().hex,
        "origin": None,
        "reading": message,
    }


def _should_relay_broadcast(message: dict[str, Any]) -> bool:
    return message.get("origin") != _WORKER_INSTANCE_ID


async def _get_publish_conn():
    global _publish_conn
    if _publish_conn is not None:
        return _publish_conn
    async with _publish_conn_lock:
        if _publish_conn is None:
            _publish_conn = aioredis.from_url(
                _REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=1,
            )
    return _publish_conn


async def _send_ws_json(websocket: WebSocket, payload: dict) -> None:
    await asyncio.wait_for(websocket.send_json(payload), timeout=_WS_SEND_TIMEOUT_SEC)


async def _broadcast_local(reading: dict):
    async with _ws_lock:
        clients = list(_ws_clients)

    if not clients:
        return

    results = await asyncio.gather(
        *(_send_ws_json(client, reading) for client in clients),
        return_exceptions=True,
    )

    dead_clients = [client for client, result in zip(clients, results, strict=True) if isinstance(result, Exception)]
    if not dead_clients:
        return

    async with _ws_lock:
        for client in dead_clients:
            if client in _ws_clients:
                _ws_clients.remove(client)


async def broadcast_reading(reading: dict):
    message = _build_broadcast_message(reading)

    if _redis_pubsub_available:
        try:
            conn = await _get_publish_conn()
            await conn.publish(_PUBSUB_CHANNEL, json.dumps(message))
        except Exception:
            logger.warning("Redis publish failed; delivering IoT reading locally only", exc_info=True)

    await _broadcast_local(message["reading"])


async def redis_subscriber_loop():
    if not _redis_pubsub_available:
        logger.info("Redis Pub/Sub unavailable; IoT WebSocket fanout is local-only")
        return

    while True:
        redis_conn = None
        pubsub = None
        try:
            redis_conn = aioredis.from_url(
                _REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
            )
            pubsub = redis_conn.pubsub()
            await pubsub.subscribe(_PUBSUB_CHANNEL)
            logger.info("Redis Pub/Sub subscriber listening on %s", _PUBSUB_CHANNEL)

            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                decoded = _decode_broadcast_message(message["data"])
                if not _should_relay_broadcast(decoded):
                    continue
                await _broadcast_local(decoded["reading"])
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Redis subscriber error: %s. Retrying in 5s.", exc)
            await asyncio.sleep(5)
        finally:
            if pubsub is not None:
                try:
                    await pubsub.close()
                except Exception:
                    logger.debug("Failed to close Redis pubsub cleanly", exc_info=True)
            if redis_conn is not None:
                try:
                    await redis_conn.close()
                except Exception:
                    logger.debug("Failed to close Redis connection cleanly", exc_info=True)


async def sensor_simulation_loop():
    while True:
        reading = _generate_mock_reading()
        _remember_local_reading(reading)
        _buffer_reading(reading)
        await broadcast_reading(reading)
        await asyncio.sleep(5)


async def batch_flush_loop():
    while True:
        try:
            if _reading_buffer:
                count = await _flush_pending_readings(max_batches=_MAX_FLUSH_BATCHES_PER_CYCLE)
                if count:
                    logger.debug("Flushed %d sensor readings", count)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Batch flush error")
        await asyncio.sleep(_FLUSH_INTERVAL_SEC)


async def add_reading_from_mqtt(sensor_msg: Any) -> None:
    reading = _with_alert_metadata(
        {
            "sensor_id": sensor_msg.sensor_id,
            "timestamp": _format_timestamp(sensor_msg.timestamp),
            "temperature": sensor_msg.temperature,
            "humidity": sensor_msg.humidity,
            "battery": sensor_msg.battery,
            "zone": sensor_msg.zone,
        }
    )

    _remember_local_reading(reading)
    _buffer_reading(reading)
    await broadcast_reading(reading)


async def handle_ws_connection(websocket: WebSocket):
    await websocket.accept()
    async with _ws_lock:
        _ws_clients.append(websocket)
    try:
        recent = get_latest_readings(hours=1)[-20:]
        await websocket.send_json({"type": "history", "data": recent})
        while True:
            await websocket.receive_text()
    except Exception as exc:
        if not isinstance(exc, asyncio.CancelledError):
            logger.debug("WebSocket client disconnected: %s", exc)
    finally:
        async with _ws_lock:
            if websocket in _ws_clients:
                _ws_clients.remove(websocket)


async def close_iot_resources() -> None:
    global _publish_conn

    if _reading_buffer:
        try:
            flushed = await _flush_pending_readings()
            if flushed:
                logger.info("Drained %d buffered IoT readings during shutdown", flushed)
            if _reading_buffer:
                logger.warning("Shutdown completed with %d IoT readings still buffered", len(_reading_buffer))
        except Exception:
            logger.exception("Failed to drain buffered IoT readings during shutdown")

    if _publish_conn is not None:
        try:
            await _publish_conn.close()
        except Exception:
            logger.debug("Failed to close Redis publisher connection cleanly", exc_info=True)
        finally:
            _publish_conn = None
