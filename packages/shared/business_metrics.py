"""
shared.business_metrics — Custom Prometheus metrics for business KPIs.

Tracks LLM token usage, API costs, and domain-specific counters
(trend hits, QR scans, RFP matches, etc.).

Usage::
    from shared.business_metrics import biz
    biz.llm_request("gpt-4o", input_tokens=500, output_tokens=200, cost_usd=0.003)
    biz.trend_scored()
    biz.tweet_published()
    biz.qr_scan()
    biz.rfp_match()

All counters are no-ops when prometheus_client is not installed.
"""
from __future__ import annotations

try:
    from prometheus_client import Counter, Histogram
    _PROM = True
except ImportError:
    _PROM = False


class _BusinessMetrics:
    """Lazy-initialized Prometheus business metrics."""

    def __init__(self):
        self._initialized = False

    def _ensure(self):
        if self._initialized or not _PROM:
            return
        self._initialized = True

        # -- LLM metrics --
        self._llm_requests = Counter(
            "llm_requests_total",
            "Total LLM API requests",
            ["service", "model"],
        )
        self._llm_tokens = Counter(
            "llm_tokens_total",
            "Total LLM tokens consumed",
            ["service", "model", "direction"],
        )
        self._llm_cost = Counter(
            "llm_cost_usd_total",
            "Cumulative LLM API cost in USD",
            ["service", "model"],
        )
        self._llm_latency = Histogram(
            "llm_request_duration_seconds",
            "LLM request latency in seconds",
            ["service", "model"],
            buckets=(0.5, 1, 2, 5, 10, 30, 60, 120),
        )

        # -- GetDayTrends --
        self._trends_scored = Counter(
            "trends_scored_total",
            "Total trends scored",
            ["service"],
        )
        self._tweets_published = Counter(
            "tweets_published_total",
            "Total tweets published to X",
            ["service"],
        )

        # -- AgriGuard --
        self._qr_scans = Counter(
            "agriguard_qr_scans_total",
            "Total QR scan events",
            ["service", "event_type"],
        )
        self._verifications = Counter(
            "agriguard_verifications_total",
            "Total product verifications completed",
            ["service"],
        )

        # -- BioLinker --
        self._rfp_matches = Counter(
            "rfp_matches_total",
            "Total RFP matching operations",
            ["service"],
        )
        self._rfp_analyses = Counter(
            "rfp_analyses_total",
            "Total RFP fit analyses",
            ["service"],
        )
        self._proposals_generated = Counter(
            "proposals_generated_total",
            "Total proposals generated",
            ["service"],
        )

    # ── LLM ────────────────────────────────────────────────────

    def llm_request(
        self,
        model: str,
        *,
        service: str = "app",
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        duration_s: float = 0.0,
    ) -> None:
        self._ensure()
        if not _PROM:
            return
        self._llm_requests.labels(service=service, model=model).inc()
        if input_tokens:
            self._llm_tokens.labels(
                service=service, model=model, direction="input"
            ).inc(input_tokens)
        if output_tokens:
            self._llm_tokens.labels(
                service=service, model=model, direction="output"
            ).inc(output_tokens)
        if cost_usd > 0:
            self._llm_cost.labels(service=service, model=model).inc(cost_usd)
        if duration_s > 0:
            self._llm_latency.labels(service=service, model=model).observe(
                duration_s
            )

    # ── GetDayTrends ───────────────────────────────────────────

    def trend_scored(self, *, service: str = "getdaytrends") -> None:
        self._ensure()
        if not _PROM:
            return
        self._trends_scored.labels(service=service).inc()

    def tweet_published(self, *, service: str = "getdaytrends") -> None:
        self._ensure()
        if not _PROM:
            return
        self._tweets_published.labels(service=service).inc()

    # ── AgriGuard ──────────────────────────────────────────────

    def qr_scan(
        self, event_type: str = "scan_start", *, service: str = "agriguard"
    ) -> None:
        self._ensure()
        if not _PROM:
            return
        self._qr_scans.labels(service=service, event_type=event_type).inc()

    def verification_complete(self, *, service: str = "agriguard") -> None:
        self._ensure()
        if not _PROM:
            return
        self._verifications.labels(service=service).inc()

    # ── BioLinker ──────────────────────────────────────────────

    def rfp_match(self, *, service: str = "biolinker") -> None:
        self._ensure()
        if not _PROM:
            return
        self._rfp_matches.labels(service=service).inc()

    def rfp_analysis(self, *, service: str = "biolinker") -> None:
        self._ensure()
        if not _PROM:
            return
        self._rfp_analyses.labels(service=service).inc()

    def proposal_generated(self, *, service: str = "biolinker") -> None:
        self._ensure()
        if not _PROM:
            return
        self._proposals_generated.labels(service=service).inc()


# Singleton — import and use directly
biz = _BusinessMetrics()
