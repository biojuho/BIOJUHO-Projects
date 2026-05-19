"""
BioLinker - RabbitMQ Message Bus
Asynchronous task orchestration.
"""

import json
import os

try:
    import pika

    PIKA_AVAILABLE = True
except ImportError:  # pragma: no cover - used in lean smoke environments
    pika = None
    PIKA_AVAILABLE = False

from services.logging_config import get_logger

log = get_logger("biolinker.services.rabbitmq_bus")


class RabbitMQBus:
    """RabbitMQ messaging bus for background jobs."""

    def __init__(self):
        self.url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672//")
        self._connection = None
        self._channel = None
        self._is_connected = False
        self._connect()

    def _connect(self):
        """Initialize RabbitMQ connection."""
        if not PIKA_AVAILABLE:
            self._is_connected = False
            log.warning("rabbitmq_dependency_missing")
            return

        try:
            params = pika.URLParameters(self.url)
            params.heartbeat = 600
            params.blocked_connection_timeout = 300

            self._connection = pika.BlockingConnection(params)
            self._channel = self._connection.channel()

            # Declare main exchange
            self._channel.exchange_declare(exchange="biolinker_events", exchange_type="topic", durable=True)

            self._is_connected = True
            log.info("rabbitmq_connected", url=self.url)
        except Exception as exc:
            self._is_connected = False
            log.warning("rabbitmq_connection_failed", url=self.url, error=str(exc))

    @property
    def is_connected(self) -> bool:
        """Check if RabbitMQ is connected."""
        if self._connection is None or self._connection.is_closed:
            self._connect()
        return self._is_connected

    def publish_job(self, routing_key: str, data: dict):
        """Publish a background job to the bus."""
        if not PIKA_AVAILABLE:
            log.error("rabbitmq_publish_failed_dependency_missing", key=routing_key)
            return False
        if not self.is_connected:
            log.error("rabbitmq_publish_failed_not_connected", key=routing_key)
            return False

        try:
            self._channel.basic_publish(
                exchange="biolinker_events",
                routing_key=routing_key,
                body=json.dumps(data),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # make message durable
                    content_type="application/json",
                ),
            )
            log.info("job_published", key=routing_key)
            return True
        except Exception as exc:
            log.error("job_publish_error", key=routing_key, error=str(exc))
            self._is_connected = False
            return False

    def close(self):
        """Gracefully close the connection."""
        if self._connection and not self._connection.is_closed:
            self._connection.close()


_rabbitmq_bus = None


def get_rabbitmq_bus() -> RabbitMQBus:
    """Singleton getter for RabbitMQ bus."""
    global _rabbitmq_bus
    if _rabbitmq_bus is None:
        _rabbitmq_bus = RabbitMQBus()
    return _rabbitmq_bus
