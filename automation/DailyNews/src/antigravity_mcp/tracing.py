"""Lightweight trace context propagation via contextvars.

Sets a ``trace_id`` (usually the pipeline ``run_id``) on the current
async/thread context so that all log records emitted within a pipeline
run automatically include it in the JSONL output.

Usage:
    from antigravity_mcp.tracing import trace_context, current_trace_id

    with trace_context(run_id):
        # All logs emitted here will include {"trace_id": run_id}
        ...

    # Or read the current trace_id:
    tid = current_trace_id()
"""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import Iterator

_trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")


def current_trace_id() -> str:
    """Return the active trace_id, or empty string if none is set."""
    return _trace_id_var.get()


@contextmanager
def trace_context(trace_id: str) -> Iterator[None]:
    """Set ``trace_id`` for the duration of the block, then restore."""
    token = _trace_id_var.set(trace_id)
    try:
        yield
    finally:
        _trace_id_var.reset(token)
