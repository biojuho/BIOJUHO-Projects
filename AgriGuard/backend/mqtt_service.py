"""
AgriGuard - MQTT IoT Sensor Integration (Phase 3)

Connects to MQTT broker (Mosquitto) for real-time sensor data collection.
Falls back to simulation mode when broker is unavailable.

Usage:
    from mqtt_service import MQTTSensorService
    service = MQTTSensorService()
    await service.start()

Requires: pip install aiomqtt>=2.0.0
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

log = logging.getLogger("agriguard.mqtt")

try:
    import aiomqtt

    _HAS_MQTT = True
except ImportError:
    _HAS_MQTT = False
    log.info("aiomqtt not installed - MQTT disabled. Install with: pip install aiomqtt>=2.0.0")


@dataclass
class SensorMessage:
    """Parsed MQTT sensor message."""

    sensor_id: str
    temperature: float
    humidity: float
    battery: float
    zone: str
    timestamp: datetime
    raw: dict[str, Any]


class MQTTSensorService:
    """MQTT client for IoT sensor data collection."""

    TOPIC_SENSORS = "agriguard/sensors/+"
    TOPIC_ALERTS = "agriguard/alerts"

    def __init__(
        self,
        broker_host: str = "localhost",
        broker_port: int = 1883,
        on_reading: Callable[[SensorMessage], Any] | None = None,
    ) -> None:
        self._host = broker_host
        self._port = broker_port
        self._on_reading = on_reading
        self._running = False
        self._client = None

    async def start(self) -> None:
        """Connect to MQTT broker and start listening."""
        if not _HAS_MQTT:
            log.warning("MQTT not available - running in simulation mode")
            return

        self._running = True
        log.info("Connecting to MQTT broker at %s:%d", self._host, self._port)

        try:
            async with aiomqtt.Client(self._host, self._port) as client:
                self._client = client
                await client.subscribe(self.TOPIC_SENSORS)
                log.info("Subscribed to %s", self.TOPIC_SENSORS)

                async for message in client.messages:
                    if not self._running:
                        break
                    await self._handle_message(message)
        except Exception as e:
            log.error("MQTT connection failed: %s", e)
            self._running = False

    async def stop(self) -> None:
        """Stop the MQTT listener."""
        self._running = False
        log.info("MQTT service stopped")

    async def publish_alert(self, product_id: str, alert_type: str, message: str) -> None:
        """Publish an alert to the alerts topic."""
        if self._client is None:
            log.warning("MQTT not connected - cannot publish alert")
            return

        payload = json.dumps({
            "product_id": product_id,
            "alert_type": alert_type,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        await self._client.publish(self.TOPIC_ALERTS, payload)

    async def _handle_message(self, message: Any) -> None:
        """Parse and dispatch an incoming MQTT message."""
        try:
            payload = json.loads(message.payload.decode())
            topic_parts = str(message.topic).split("/")
            sensor_id = topic_parts[-1] if len(topic_parts) > 2 else "unknown"

            reading = SensorMessage(
                sensor_id=sensor_id,
                temperature=float(payload.get("temperature", 0)),
                humidity=float(payload.get("humidity", 0)),
                battery=float(payload.get("battery", 100)),
                zone=payload.get("zone", "unknown"),
                timestamp=datetime.now(timezone.utc),
                raw=payload,
            )

            # Check thresholds
            if reading.temperature > 8 or reading.temperature < -25:
                log.warning(
                    "Temperature alert: sensor=%s temp=%.1f°C",
                    reading.sensor_id,
                    reading.temperature,
                )
                await self.publish_alert(
                    product_id=payload.get("product_id", ""),
                    alert_type="temperature_violation",
                    message=f"Sensor {reading.sensor_id}: {reading.temperature}°C",
                )

            if self._on_reading:
                result = self._on_reading(reading)
                if asyncio.iscoroutine(result):
                    await result

        except (json.JSONDecodeError, ValueError) as e:
            log.warning("Invalid MQTT message: %s", e)
