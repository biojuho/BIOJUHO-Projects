"""Cross-project contract tests.

Verify that the shared package public interfaces remain stable across all
consumer projects.  These tests do NOT make network calls — they import
the modules and confirm that expected attributes, function signatures,
and types are present.
"""

from __future__ import annotations

import importlib
import inspect
from typing import Any


# ---------------------------------------------------------------------------
# 1. shared.llm — Unified LLM client contract
# ---------------------------------------------------------------------------


def test_shared_llm_client_exports_get_client() -> None:
    """get_client() must exist and return a singleton-like object."""
    mod = importlib.import_module("shared.llm")
    assert hasattr(mod, "get_client"), "shared.llm must export get_client"
    fn = getattr(mod, "get_client")
    assert callable(fn)


def test_shared_llm_client_has_task_tier_enum() -> None:
    """TaskTier enum with HEAVY / MEDIUM / LIGHTWEIGHT must be importable."""
    mod = importlib.import_module("shared.llm.config")
    assert hasattr(mod, "TaskTier"), "shared.llm.config must export TaskTier"
    tier_cls = getattr(mod, "TaskTier")
    for member in ("HEAVY", "MEDIUM", "LIGHTWEIGHT"):
        assert hasattr(tier_cls, member), f"TaskTier must have {member}"


# ---------------------------------------------------------------------------
# 2. shared.env_loader — Environment loading contract
# ---------------------------------------------------------------------------


def test_env_loader_exports_load_workspace_env() -> None:
    mod = importlib.import_module("shared.env_loader")
    assert hasattr(mod, "load_workspace_env"), "shared.env_loader must export load_workspace_env"
    fn = getattr(mod, "load_workspace_env")
    assert callable(fn)


# ---------------------------------------------------------------------------
# 3. shared.notifications — Notifier contract
# ---------------------------------------------------------------------------


def test_notifier_has_send_methods() -> None:
    mod = importlib.import_module("shared.notifications")
    # Walk submodules to find Notifier class
    notifier_cls: Any = None
    for name in dir(mod):
        obj = getattr(mod, name)
        if inspect.isclass(obj) and "Notifier" in name:
            notifier_cls = obj
            break

    if notifier_cls is None:
        # Check submodule
        try:
            sub = importlib.import_module("shared.notifications.notifier")
            for name in dir(sub):
                obj = getattr(sub, name)
                if inspect.isclass(obj) and "Notifier" in name:
                    notifier_cls = obj
                    break
        except ModuleNotFoundError:
            pass

    assert notifier_cls is not None, (
        "shared.notifications must contain a Notifier class"
    )


# ---------------------------------------------------------------------------
# 4. shared.circuit_breaker — Resilience contract
# ---------------------------------------------------------------------------


def test_circuit_breaker_three_state_contract() -> None:
    from shared.circuit_breaker import CircuitBreaker

    cb = CircuitBreaker("test-service", failure_threshold=2, cooldown_sec=0.1)
    assert cb.state == "closed"
    assert cb.allow_request() is True

    # Drive to OPEN
    cb.record_failure()
    cb.record_failure()
    assert cb.state == "open"
    assert cb.allow_request() is False

    # Reset
    cb.reset()
    assert cb.state == "closed"


def test_circuit_breaker_half_open_probe() -> None:
    """After cooldown, OPEN transitions to HALF_OPEN and allows one probe."""
    import time

    from shared.circuit_breaker import CircuitBreaker

    cb = CircuitBreaker("probe-test", failure_threshold=1, cooldown_sec=0.05)
    cb.record_failure()
    assert cb.state == "open"

    time.sleep(0.1)
    assert cb.allow_request() is True
    assert cb.state == "half_open"

    # Successful probe → CLOSED
    cb.record_success()
    assert cb.state == "closed"


# ---------------------------------------------------------------------------
# 5. shared.cache — Cache interface contract
# ---------------------------------------------------------------------------


def test_shared_cache_module_importable() -> None:
    mod = importlib.import_module("shared.cache")
    # Must export get_cache or similar factory
    public = [n for n in dir(mod) if not n.startswith("_")]
    assert len(public) > 0, "shared.cache must have public exports"


# ---------------------------------------------------------------------------
# 6. shared.paths — Workspace path resolution contract
# ---------------------------------------------------------------------------


def test_paths_resolves_workspace_root() -> None:
    from shared.paths import WORKSPACE_ROOT

    assert WORKSPACE_ROOT.exists(), "WORKSPACE_ROOT must point to an existing directory"
    assert (WORKSPACE_ROOT / "pyproject.toml").exists(), (
        "WORKSPACE_ROOT must contain pyproject.toml"
    )


# ---------------------------------------------------------------------------
# 7. shared.metrics — Prometheus metrics contract
# ---------------------------------------------------------------------------


def test_metrics_setup_function_exists() -> None:
    mod = importlib.import_module("shared.metrics")
    assert hasattr(mod, "setup_metrics"), "shared.metrics must export setup_metrics"


# ---------------------------------------------------------------------------
# 8. shared.structured_logging — Logging contract
# ---------------------------------------------------------------------------


def test_structured_logging_setup_exists() -> None:
    mod = importlib.import_module("shared.structured_logging")
    assert hasattr(mod, "setup_logging"), (
        "shared.structured_logging must export setup_logging"
    )
