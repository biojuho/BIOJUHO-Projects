"""shared.llm.stats - Cost tracking and usage statistics."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .config import MODEL_COSTS
from .models import CostRecord, TaskTier


@dataclass
class UsageStats:
    """Aggregated usage statistics."""

    total_calls: int = 0
    total_errors: int = 0
    total_cost_usd: float = 0.0
    calls_by_backend: dict[str, int] = field(default_factory=dict)
    calls_by_tier: dict[str, int] = field(default_factory=dict)
    cost_by_backend: dict[str, float] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return round((self.total_calls - self.total_errors) / self.total_calls * 100, 1)


class CostTracker:
    """Thread-safe cost tracking for LLM calls."""

    def __init__(self) -> None:
        self._records: list[CostRecord] = []
        self._lock = threading.Lock()

    def record(
        self,
        backend: str,
        model: str,
        tier: TaskTier,
        input_tokens: int = 0,
        output_tokens: int = 0,
        success: bool = True,
        error: str = "",
    ) -> CostRecord:
        """Record a single LLM call."""
        cost_per_m = MODEL_COSTS.get(model, (0.0, 0.0))
        cost = (input_tokens * cost_per_m[0] + output_tokens * cost_per_m[1]) / 1_000_000

        rec = CostRecord(
            timestamp=datetime.now(timezone.utc),
            backend=backend,
            model=model,
            tier=tier,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            success=success,
            error=error,
        )
        with self._lock:
            self._records.append(rec)
        return rec

    def get_stats(self) -> UsageStats:
        """Compute aggregated stats from all records."""
        with self._lock:
            records = list(self._records)

        stats = UsageStats()
        for r in records:
            stats.total_calls += 1
            if not r.success:
                stats.total_errors += 1
            stats.total_cost_usd += r.cost_usd
            stats.calls_by_backend[r.backend] = stats.calls_by_backend.get(r.backend, 0) + 1
            stats.calls_by_tier[r.tier.value] = stats.calls_by_tier.get(r.tier.value, 0) + 1
            stats.cost_by_backend[r.backend] = stats.cost_by_backend.get(r.backend, 0) + r.cost_usd

        stats.total_cost_usd = round(stats.total_cost_usd, 6)
        for k in stats.cost_by_backend:
            stats.cost_by_backend[k] = round(stats.cost_by_backend[k], 6)
        return stats

    def reset(self) -> None:
        """Clear all records."""
        with self._lock:
            self._records.clear()
