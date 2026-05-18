"""
BioLinker - Redis Store Service
Centralized caching and session management.
"""

import os
import redis
from services.logging_config import get_logger

log = get_logger("biolinker.services.redis_store")

class RedisStore:
    """Redis storage and caching service."""

    def __init__(self):
        self.url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._client = None
        self._is_ready = False
        self._connect()

    def _connect(self):
        """Initialize Redis connection."""
        try:
            self._client = redis.from_url(self.url, decode_responses=True)
            # Test connection
            self._client.ping()
            self._is_ready = True
            log.info("redis_connected", url=self.url)
        except Exception as exc:
            self._is_ready = False
            log.warning("redis_connection_failed", url=self.url, error=str(exc))

    @property
    def is_ready(self) -> bool:
        """Check if Redis is connected and responsive."""
        if not self._is_ready:
            self._connect()
        return self._is_ready

    def get(self, key: str):
        """Get value from Redis."""
        if not self.is_ready:
            return None
        try:
            return self._client.get(key)
        except Exception as exc:
            log.warning("redis_get_error", key=key, error=str(exc))
            return None

    def set(self, key: str, value: str, ex: int | None = None):
        """Set value in Redis with optional expiration."""
        if not self.is_ready:
            return False
        try:
            return self._client.set(key, value, ex=ex)
        except Exception as exc:
            log.warning("redis_set_error", key=key, error=str(exc))
            return False

_redis_store = None

def get_redis_store() -> RedisStore:
    """Singleton getter for Redis store."""
    global _redis_store
    if _redis_store is None:
        _redis_store = RedisStore()
    return _redis_store
