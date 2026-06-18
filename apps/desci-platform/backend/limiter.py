"""
BioLinker - Shared rate limiter instance.
Import this in routers that need @limiter.limit(...) decorators.
"""

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
except ImportError:  # pragma: no cover - used in lean smoke environments
    Limiter = None  # type: ignore[assignment]
    get_remote_address = None  # type: ignore[assignment]


class _NoopLimiter:
    def limit(self, _rule: str):
        def decorator(func):
            return func

        return decorator


limiter = Limiter(key_func=get_remote_address) if Limiter is not None else _NoopLimiter()
