"""
AgriGuard IoT Service — Cold-Chain Temperature & Humidity Monitoring
Simulates IoT sensor data (mock) and provides WebSocket + REST endpoints.
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Any

from database import SessionLocal
from fastapi import WebSocket
from models import SensorReading

logger = logging.getLogger(__name__)

# In-memory storage for sensor readings
_sensor_history: list[dict] = []
_MAX_HISTORY = 2000  # Keep last 2000 readings
_ALERT_THRESHOLDS = {
    "temp_min": -25.0,
    "temp_max": 8.0,
    "humidity_min": 30.0,
    "humidity_max": 85.0,
}

# Active WebSocket connections — guarded by _ws_lock
_ws_clients: list[WebSocket] = []
_ws_lock = asyncio.Lock()


def _generate_mock_reading() -> dict:
    """Generate a realistic cold-chain sensor reading."""
    now = datetime.now()
    # Simulate slight temperature drift
    base_temp = -18.0 + random.gauss(0, 1.5)
    base_humidity = 55.0 + random.gauss(0, 5)

    # Occasionally simulate anomalies (5% chance)
    if random.random() < 0.05:
        base_temp += random.choice([-10, 15, 20])  # Spike

    reading = {
        "sensor_id": f"SENSOR-{random.choice(['A1', 'A2', 'B1', 'B2', 'C1'])}",
        "timestamp": now.isoformat(),
        "temperature": round(max(-30, min(50, base_temp)), 1),
        "humidity": round(max(0, min(100, base_humidity)), 1),
        "battery": round(random.uniform(60, 100), 0),
        "zone": random.choice(["Cold Storage A", "Cold Storage B", "Transport Unit 1", "Transport Unit 2"]),
    }

    # Check alerts
    alerts = []
    if reading["temperature"] < _ALERT_THRESHOLDS["temp_min"]:
        alerts.append(f"🥶 Temperature too low: {reading['temperature']}°C")
    elif reading["temperature"] > _ALERT_THRESHOLDS["temp_max"]:
        alerts.append(f"🔥 Temperature too high: {reading['temperature']}°C")
    if reading["humidity"] < _ALERT_THRESHOLDS["humidity_min"]:
        alerts.append(f"💧 Humidity too low: {reading['humidity']}%")
    elif reading["humidity"] > _ALERT_THRESHOLDS["humidity_max"]:
        alerts.append(f"💦 Humidity too high: {reading['humidity']}%")

    reading["alerts"] = alerts
    reading["status"] = "alert" if alerts else "normal"
    return reading


def _persist_reading(reading: dict) -> None:
    """Persist a sensor reading to the database."""
    db = SessionLocal()
    try:
        sensor_reading = SensorReading(
            sensor_id=reading["sensor_id"],
            timestamp=datetime.fromisoformat(reading["timestamp"]),
            temperature=reading["temperature"],
            humidity=reading["humidity"],
            battery=reading["battery"],
            zone=reading["zone"],
            status=reading["status"],
        )
        db.add(sensor_reading)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to persist sensor reading")
    finally:
        db.close()


def get_latest_readings(hours: int = 24) -> list[dict]:
    """Get sensor readings from the last N hours."""
    cutoff = datetime.now() - timedelta(hours=hours)
    return [r for r in _sensor_history if datetime.fromisoformat(r["timestamp"]) > cutoff]


def get_current_status() -> dict:
    """Get aggregated current status of all zones."""
    recent = get_latest_readings(hours=1)
    if not recent:
        return {"zones": [], "overall_status": "no_data"}

    zones = {}
    for r in recent:
        zone = r["zone"]
        if zone not in zones:
            zones[zone] = {"temps": [], "humidities": [], "alerts": 0}
        zones[zone]["temps"].append(r["temperature"])
        zones[zone]["humidities"].append(r["humidity"])
        if r["status"] == "alert":
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

    has_alerts = any(z["alert_count"] > 0 for z in result)
    return {
        "zones": result,
        "overall_status": "alert" if has_alerts else "normal",
        "total_readings": len(recent),
    }


async def broadcast_reading(reading: dict):
    """Broadcast a sensor reading to all connected WebSocket clients."""
    dead = []
    async with _ws_lock:
        for ws in _ws_clients:
            try:
                await ws.send_json(reading)
            except Exception:
                dead.append(ws)
        for ws in dead:
            _ws_clients.remove(ws)


async def sensor_simulation_loop():
    """Background task: generate mock sensor data every 5 seconds."""
    while True:
        reading = _generate_mock_reading()
        _sensor_history.append(reading)

        # Trim history
        if len(_sensor_history) > _MAX_HISTORY:
            _sensor_history[:] = _sensor_history[-_MAX_HISTORY:]

        # Persist to database (run in thread to avoid blocking the event loop)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _persist_reading, reading)

        # Broadcast to WebSocket clients
        await broadcast_reading(reading)
        await asyncio.sleep(5)


async def add_reading_from_mqtt(sensor_msg: Any) -> None:
    """Ingest a SensorMessage from the MQTT service into the IoT pipeline.

    Accepts a mqtt_service.SensorMessage dataclass, converts it to the
    standard reading dict, persists it to the DB, and broadcasts it to all
    connected WebSocket clients.
    """
    # Determine alert status using the same thresholds as the simulator
    alerts: list[str] = []
    if sensor_msg.temperature < _ALERT_THRESHOLDS["temp_min"]:
        alerts.append(f"Temperature too low: {sensor_msg.temperature}°C")
    elif sensor_msg.temperature > _ALERT_THRESHOLDS["temp_max"]:
        alerts.append(f"Temperature too high: {sensor_msg.temperature}°C")
    if sensor_msg.humidity < _ALERT_THRESHOLDS["humidity_min"]:
        alerts.append(f"Humidity too low: {sensor_msg.humidity}%")
    elif sensor_msg.humidity > _ALERT_THRESHOLDS["humidity_max"]:
        alerts.append(f"Humidity too high: {sensor_msg.humidity}%")

    reading: dict = {
        "sensor_id": sensor_msg.sensor_id,
        "timestamp": sensor_msg.timestamp.isoformat(),
        "temperature": sensor_msg.temperature,
        "humidity": sensor_msg.humidity,
        "battery": sensor_msg.battery,
        "zone": sensor_msg.zone,
        "alerts": alerts,
        "status": "alert" if alerts else "normal",
    }

    _sensor_history.append(reading)

    # Trim history
    if len(_sensor_history) > _MAX_HISTORY:
        _sensor_history[:] = _sensor_history[-_MAX_HISTORY:]

    # Persist to DB without blocking the event loop
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _persist_reading, reading)

    # Broadcast to WebSocket clients
    await broadcast_reading(reading)


async def handle_ws_connection(websocket: WebSocket):
    """Handle a WebSocket client connection for live IoT data."""
    await websocket.accept()
    async with _ws_lock:
        _ws_clients.append(websocket)
    try:
        # Send recent history on connect
        recent = get_latest_readings(hours=1)[-20:]
        await websocket.send_json({"type": "history", "data": recent})

        # Keep alive
        while True:
            await websocket.receive_text()
    except Exception:
        pass
    finally:
        async with _ws_lock:
            if websocket in _ws_clients:
                _ws_clients.remove(websocket)
