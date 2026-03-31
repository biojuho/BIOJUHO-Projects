"""Base class for state store mixins.

Provides the ``_connect()`` contract so mixins no longer need
``raise NotImplementedError`` stubs.
"""

from __future__ import annotations

import sqlite3
from typing import Protocol


class _DBProvider(Protocol):
    """Protocol satisfied by PipelineStateStore.

    Mixins that need database access should inherit from ``_DBProviderBase``
    (the concrete base) instead of defining their own ``_connect`` stub.
    """

    def _connect(self) -> sqlite3.Connection: ...


class _DBProviderBase:
    """Concrete base class for mixins that access the SQLite connection.

    PipelineStateStore provides the real ``_connect`` implementation.
    Mixins inherit this class so they get the method signature without
    duplicating ``_connect()`` stubs everywhere.
    """

    def _connect(self) -> sqlite3.Connection:
        raise NotImplementedError("_connect() must be provided by PipelineStateStore")
