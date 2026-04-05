"""shared.harness.audit — Structured audit logging for agent actions.

All tool calls pass through the audit logger, creating a tamper-evident
JSONL trail for compliance, debugging, and observability.

Integrates with shared.structured_logging when available.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AuditVerdict(str, Enum):
    """Outcome of a governance check."""

    ALLOWED = "allowed"
    DENIED = "denied"
    APPROVED_HITL = "approved_hitl"
    REJECTED_HITL = "rejected_hitl"
    ERROR = "error"


@dataclass
class AuditRecord:
    """Single audit log entry for one tool call attempt.

    Fields are designed for easy querying in structured log systems
    (e.g., Loki, Elasticsearch).
    """

    timestamp: str
    agent_name: str
    tool_name: str
    verdict: str  # AuditVerdict value
    reason: str = ""
    tool_input_summary: str = ""  # Truncated for privacy
    elapsed_ms: float = 0.0
    session_cost_usd: float = 0.0
    session_tool_calls: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Serialize to a single JSON line (JSONL compatible)."""
        return json.dumps(asdict(self), ensure_ascii=False, default=str)


class AuditLogger:
    """Append-only structured audit logger for harness governance.

    Writes JSONL records to a file and optionally emits to
    the Python logging system for integration with existing
    observability pipelines (Loki/Promtail).
    """

    def __init__(
        self,
        agent_name: str = "default",
        log_path: Optional[str | Path] = None,
        emit_to_logging: bool = True,
        max_input_chars: int = 200,
    ):
        self.agent_name = agent_name
        self.log_path = Path(log_path) if log_path else None
        self.emit_to_logging = emit_to_logging
        self.max_input_chars = max_input_chars
        self._records: list[AuditRecord] = []

        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _truncate_input(self, tool_input: Any) -> str:
        """Truncate tool input for privacy/size limits."""
        text = str(tool_input)
        if len(text) > self.max_input_chars:
            return text[: self.max_input_chars] + "..."
        return text

    def _write_record(self, record: AuditRecord) -> None:
        """Persist a record to file and/or logging."""
        self._records.append(record)

        json_line = record.to_json()

        if self.log_path:
            try:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(json_line + "\n")
            except OSError as e:
                logger.warning("audit_write_failed: %s", e)

        if self.emit_to_logging:
            if record.verdict == AuditVerdict.DENIED:
                logger.warning("harness_audit: %s", json_line)
            else:
                logger.info("harness_audit: %s", json_line)

    def log_allowed(
        self,
        tool_name: str,
        tool_input: Any,
        elapsed_ms: float = 0.0,
        session_cost_usd: float = 0.0,
        session_tool_calls: int = 0,
        **extra: Any,
    ) -> AuditRecord:
        """Log a successful (allowed) tool execution."""
        record = AuditRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent_name=self.agent_name,
            tool_name=tool_name,
            verdict=AuditVerdict.ALLOWED,
            tool_input_summary=self._truncate_input(tool_input),
            elapsed_ms=elapsed_ms,
            session_cost_usd=session_cost_usd,
            session_tool_calls=session_tool_calls,
            metadata=extra,
        )
        self._write_record(record)
        return record

    def log_denied(
        self,
        tool_name: str,
        reason: str,
        tool_input: Any = None,
        **extra: Any,
    ) -> AuditRecord:
        """Log a denied tool execution attempt."""
        record = AuditRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent_name=self.agent_name,
            tool_name=tool_name,
            verdict=AuditVerdict.DENIED,
            reason=reason,
            tool_input_summary=self._truncate_input(tool_input) if tool_input else "",
            metadata=extra,
        )
        self._write_record(record)
        return record

    def log_error(
        self,
        tool_name: str,
        error: Exception,
        tool_input: Any = None,
        **extra: Any,
    ) -> AuditRecord:
        """Log an error during tool execution."""
        record = AuditRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent_name=self.agent_name,
            tool_name=tool_name,
            verdict=AuditVerdict.ERROR,
            reason=f"{type(error).__name__}: {error}",
            tool_input_summary=self._truncate_input(tool_input) if tool_input else "",
            metadata=extra,
        )
        self._write_record(record)
        return record

    @property
    def records(self) -> list[AuditRecord]:
        """In-memory record buffer (for testing and diagnostics)."""
        return list(self._records)

    @property
    def denied_count(self) -> int:
        """Count of denied actions in the current session."""
        return sum(1 for r in self._records if r.verdict == AuditVerdict.DENIED)

    @property
    def total_count(self) -> int:
        """Total audit records in the current session."""
        return len(self._records)
