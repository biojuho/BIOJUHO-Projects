from collections.abc import Generator
from typing import Any

from auth import get_current_user
from database import SessionLocal
from fastapi import Depends
from sqlalchemy.orm import Session
from tenant_rls import apply_tenant_rls_context


def get_db() -> Generator[Any, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_tenant_rls_db(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Session:
    apply_tenant_rls_context(db, current_user)
    return db


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

        def get_cache() -> _NoOpCache:
            return _CACHE_FALLBACK

        async def close_cache() -> None:
            await _CACHE_FALLBACK.close()
