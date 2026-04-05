from database import SessionLocal
from typing import Any

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

try:
    from shared.cache import close_cache, get_cache
except ImportError:
    try:
        from packages.shared.cache import close_cache, get_cache
    except ImportError:
        class _NoOpCache:
            '''Safe fallback when the shared cache package is unavailable.'''
            async def get(self, key: str) -> Any: return None
            async def set(self, key: str, value: Any, ttl: int = 60) -> None: pass
            async def delete(self, key: str) -> None: pass
            async def exists(self, key: str) -> bool: return False
            async def incr(self, key: str, ttl: int = 60) -> int: return 1
            async def close(self) -> None: pass

        _CACHE_FALLBACK = _NoOpCache()

        def get_cache():
            return _CACHE_FALLBACK

        async def close_cache() -> None:
            await _CACHE_FALLBACK.close()
