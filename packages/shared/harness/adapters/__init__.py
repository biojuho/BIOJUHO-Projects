"""shared.harness.adapters — Adapter layer for external harness frameworks.

비유: 전원 어댑터 — 다른 규격의 프레임워크를 우리 콘센트에 꽂을 수 있게 함.

Provides a common interface so that native HarnessWrapper, DeepAgents,
or any future framework can be used interchangeably as the governance
engine for our pipelines.
"""

from .base import AbstractHarnessAdapter, AdapterResult
from .native import NativeHarnessAdapter
from .deepagents import DeepAgentsAdapter

__all__ = [
    "AbstractHarnessAdapter",
    "AdapterResult",
    "NativeHarnessAdapter",
    "DeepAgentsAdapter",
]
