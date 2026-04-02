"""Re-export shim — CircuitBreaker has moved to shared.circuit_breaker."""

from shared.circuit_breaker import CircuitBreaker

__all__ = ["CircuitBreaker"]
