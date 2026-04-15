"""BioLinker service package exports."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_LAZY_SUBMODULES = {"pdf_parser"}

__all__ = ["pdf_parser"]


def __getattr__(name: str) -> Any:
    if name in _LAZY_SUBMODULES:
        return import_module(f"{__name__}.{name}")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | _LAZY_SUBMODULES)
