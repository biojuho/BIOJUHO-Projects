"""Agent ledger — per-run observability record for automation pipelines.

Writes one JSON file per pipeline run under ``var/ledger/{agent}/{date}_{run_id}.json``.
The schema is additive and versioned: new fields can be added without breaking
downstream consumers, and old entries remain readable.

This module is a pure observer. It never raises on I/O failure — a broken
ledger write must NEVER take down the pipeline that invoked it.

Typical usage::

    from datetime import UTC, datetime
    from shared.telemetry.agent_ledger import write_ledger_entry

    started = datetime.now(UTC)
    # ... run pipeline ...
    write_ledger_entry(
        agent="dailynews-morning",
        run_id=run_id,
        started_at=started,
        finished_at=datetime.now(UTC),
        status="success",
        cost_usd=0.12,
        outcomes={"notion_ok": True, "telegram_ok": True, "articles": 23},
        metadata={"window": "morning", "target_db": db_id},
    )
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LEDGER_SCHEMA_VERSION = 1
"""Bump when a breaking schema change is introduced.

Version 1 fields:
    schema_version, agent, run_id, started_at, finished_at, duration_s,
    status, cost_usd, tokens_input, tokens_output, outcomes, metadata
"""

_WORKSPACE_MARKER = "workspace-map.json"


def _discover_workspace_root() -> Path | None:
    """Walk up from this file to find the workspace root (workspace-map.json)."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / _WORKSPACE_MARKER).exists():
            return parent
    return None


def _ledger_root() -> Path:
    """Resolve the ledger root directory.

    Priority:
      1. ``AGENT_LEDGER_ROOT`` env var (used by tests and custom deployments)
      2. ``<workspace_root>/var/ledger`` when ``workspace-map.json`` is found
      3. ``<cwd>/var/ledger`` as last-resort fallback
    """
    override = os.environ.get("AGENT_LEDGER_ROOT")
    if override:
        return Path(override)
    workspace = _discover_workspace_root()
    if workspace is not None:
        return workspace / "var" / "ledger"
    return Path.cwd() / "var" / "ledger"


def build_ledger_entry(
    agent: str,
    run_id: str,
    started_at: datetime,
    finished_at: datetime,
    status: str,
    *,
    cost_usd: float = 0.0,
    tokens_input: int = 0,
    tokens_output: int = 0,
    outcomes: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a ledger entry dict without writing it. Useful for tests."""
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=UTC)
    if finished_at.tzinfo is None:
        finished_at = finished_at.replace(tzinfo=UTC)
    duration_s = (finished_at - started_at).total_seconds()
    return {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "agent": agent,
        "run_id": run_id or "unknown",
        "started_at": started_at.astimezone(UTC).isoformat(),
        "finished_at": finished_at.astimezone(UTC).isoformat(),
        "duration_s": round(duration_s, 3),
        "status": status,
        "cost_usd": round(float(cost_usd), 6),
        "tokens_input": int(tokens_input),
        "tokens_output": int(tokens_output),
        "outcomes": dict(outcomes) if outcomes else {},
        "metadata": dict(metadata) if metadata else {},
    }


def write_ledger_entry(
    agent: str,
    run_id: str,
    started_at: datetime,
    finished_at: datetime,
    status: str,
    *,
    cost_usd: float = 0.0,
    tokens_input: int = 0,
    tokens_output: int = 0,
    outcomes: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Path | None:
    """Write a ledger entry to disk. Returns the written path, or None on failure.

    This function NEVER raises. Any I/O error is caught and reported to stderr,
    and the function returns None. Pipelines can safely call it in their
    end-of-run path without a try/except wrapper.
    """
    entry = build_ledger_entry(
        agent=agent,
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        status=status,
        cost_usd=cost_usd,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        outcomes=outcomes,
        metadata=metadata,
    )
    try:
        date_str = started_at.astimezone(UTC).strftime("%Y-%m-%d")
        run_suffix = (run_id or "unknown")[:8] or "unknown"
        out_dir = _ledger_root() / agent
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{date_str}_{run_suffix}.json"
        out_path.write_text(
            json.dumps(entry, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return out_path
    except OSError as exc:
        print(
            f"[agent_ledger] failed to write entry for {agent}/{run_id}: {exc}",
            file=sys.stderr,
        )
        return None


__all__ = [
    "LEDGER_SCHEMA_VERSION",
    "build_ledger_entry",
    "write_ledger_entry",
]
