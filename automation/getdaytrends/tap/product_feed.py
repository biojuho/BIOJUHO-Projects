"""
Product-layer scaffolding for TAP (Trend Arbitrage Publisher).

This module turns raw arbitrage detections into a productizable board payload
that can later power:
1. premium "first-mover" dashboards,
2. teaser/public feeds,
3. paid alerts and API responses.

The implementation is intentionally lightweight for phase 1. It focuses on
deterministic packaging, clear interfaces, and zero new hard dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from typing import Any

try:
    from .detector import ArbitrageOpportunity
except ImportError:
    from detector import ArbitrageOpportunity


FUTURE_LIBRARY_HINTS: tuple[str, ...] = (
    "rapidfuzz>=3.9.0",
    "orjson>=3.10.0",
    "redis>=5.0.0",
)


class OpportunityTier(str, Enum):
    """Visibility tier for growth loops and monetization packaging."""

    FREE_TEASER = "free_teaser"
    PREMIUM = "premium"
    INTERNAL = "internal"


@dataclass(slots=True)
class PublishWindow:
    """Recommended execution window for a target market."""

    urgency_label: str
    opens_in_minutes: int
    closes_in_minutes: int
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "urgency_label": self.urgency_label,
            "opens_in_minutes": self.opens_in_minutes,
            "closes_in_minutes": self.closes_in_minutes,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "PublishWindow | None":
        if not payload:
            return None
        return cls(
            urgency_label=str(payload.get("urgency_label", "")),
            opens_in_minutes=int(payload.get("opens_in_minutes", 0) or 0),
            closes_in_minutes=int(payload.get("closes_in_minutes", 0) or 0),
            rationale=str(payload.get("rationale", "")),
        )


@dataclass(slots=True)
class RevenuePlay:
    """Commercial packaging hint for future conversion flows."""

    playbook_type: str
    pricing_hint: str
    cta_strategy: str
    reasoning: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "playbook_type": self.playbook_type,
            "pricing_hint": self.pricing_hint,
            "cta_strategy": self.cta_strategy,
            "reasoning": self.reasoning,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "RevenuePlay | None":
        if not payload:
            return None
        return cls(
            playbook_type=str(payload.get("playbook_type", "")),
            pricing_hint=str(payload.get("pricing_hint", "")),
            cta_strategy=str(payload.get("cta_strategy", "")),
            reasoning=str(payload.get("reasoning", "")),
        )


@dataclass(slots=True)
class TapBoardItem:
    """One user-facing arbitrage board item."""

    keyword: str
    source_country: str
    target_countries: list[str] = field(default_factory=list)
    viral_score: int = 0
    priority: float = 0.0
    time_gap_hours: float = 0.0
    paywall_tier: OpportunityTier = OpportunityTier.PREMIUM
    public_teaser: str = ""
    recommended_platforms: list[str] = field(default_factory=list)
    recommended_angle: str = ""
    execution_notes: list[str] = field(default_factory=list)
    publish_window: PublishWindow | None = None
    revenue_play: RevenuePlay | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "keyword": self.keyword,
            "source_country": self.source_country,
            "target_countries": list(self.target_countries),
            "viral_score": self.viral_score,
            "priority": self.priority,
            "time_gap_hours": self.time_gap_hours,
            "paywall_tier": self.paywall_tier.value,
            "public_teaser": self.public_teaser,
            "recommended_platforms": list(self.recommended_platforms),
            "recommended_angle": self.recommended_angle,
            "execution_notes": list(self.execution_notes),
            "publish_window": self.publish_window.to_dict() if self.publish_window else None,
            "revenue_play": self.revenue_play.to_dict() if self.revenue_play else None,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TapBoardItem":
        return cls(
            keyword=str(payload.get("keyword", "")),
            source_country=str(payload.get("source_country", "")),
            target_countries=[str(item) for item in payload.get("target_countries", []) or []],
            viral_score=int(payload.get("viral_score", 0) or 0),
            priority=float(payload.get("priority", 0.0) or 0.0),
            time_gap_hours=float(payload.get("time_gap_hours", 0.0) or 0.0),
            paywall_tier=_coerce_tier(payload.get("paywall_tier")),
            public_teaser=str(payload.get("public_teaser", "")),
            recommended_platforms=[str(item) for item in payload.get("recommended_platforms", []) or []],
            recommended_angle=str(payload.get("recommended_angle", "")),
            execution_notes=[str(item) for item in payload.get("execution_notes", []) or []],
            publish_window=PublishWindow.from_dict(payload.get("publish_window")),
            revenue_play=RevenuePlay.from_dict(payload.get("revenue_play")),
        )

    def clone_for_tier(self, paywall_tier: OpportunityTier) -> "TapBoardItem":
        return replace(self, paywall_tier=paywall_tier)


@dataclass(slots=True)
class TapBoard:
    """Phase-1 delivery contract for dashboard/API consumers."""

    generated_at: str
    target_country: str
    total_detected: int = 0
    teaser_count: int = 0
    snapshot_id: str = ""
    items: list[TapBoardItem] = field(default_factory=list)
    snapshot_source: str = "tap_service"
    delivery_mode: str = "live"
    future_dependencies: list[str] = field(default_factory=lambda: list(FUTURE_LIBRARY_HINTS))

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "generated_at": self.generated_at,
            "target_country": self.target_country,
            "total_detected": self.total_detected,
            "teaser_count": self.teaser_count,
            "items": [item.to_dict() for item in self.items],
            "snapshot_source": self.snapshot_source,
            "delivery_mode": self.delivery_mode,
            "future_dependencies": list(self.future_dependencies),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TapBoard":
        future_dependencies = payload.get("future_dependencies")
        return cls(
            snapshot_id=str(payload.get("snapshot_id", "")),
            generated_at=str(payload.get("generated_at", "")),
            target_country=str(payload.get("target_country", "")),
            total_detected=int(payload.get("total_detected", 0) or 0),
            teaser_count=int(payload.get("teaser_count", 0) or 0),
            items=[TapBoardItem.from_dict(item) for item in payload.get("items", []) or []],
            snapshot_source=str(payload.get("snapshot_source", "tap_service")),
            delivery_mode=str(payload.get("delivery_mode", "live")),
            future_dependencies=(
                [str(item) for item in future_dependencies]
                if future_dependencies is not None
                else list(FUTURE_LIBRARY_HINTS)
            ),
        )

    def clone_for_delivery(
        self,
        *,
        limit: int | None = None,
        teaser_count: int | None = None,
        delivery_mode: str | None = None,
    ) -> "TapBoard":
        resolved_limit = len(self.items) if limit is None else max(0, limit)
        resolved_teaser = self.teaser_count if teaser_count is None else max(0, teaser_count)
        projected_items = [
            item.clone_for_tier(OpportunityTier.FREE_TEASER if index < resolved_teaser else OpportunityTier.PREMIUM)
            for index, item in enumerate(self.items[:resolved_limit])
        ]
        return TapBoard(
            snapshot_id=self.snapshot_id,
            generated_at=self.generated_at,
            target_country=self.target_country,
            total_detected=self.total_detected,
            teaser_count=resolved_teaser,
            items=projected_items,
            snapshot_source=self.snapshot_source,
            delivery_mode=delivery_mode or self.delivery_mode,
            future_dependencies=list(self.future_dependencies),
        )


def empty_tap_board(*, target_country: str = "", teaser_count: int = 0) -> TapBoard:
    """Return an empty but schema-stable response."""

    return TapBoard(
        generated_at=datetime.utcnow().isoformat(),
        target_country=target_country,
        total_detected=0,
        teaser_count=teaser_count,
        items=[],
    )


class TapBoardBuilder:
    """Builds a premium-ready TAP board from raw arbitrage detections."""

    DEFAULT_LIMIT = 10
    DEFAULT_TEASER_COUNT = 3

    def build(
        self,
        opportunities: list[ArbitrageOpportunity] | None,
        *,
        target_country: str = "",
        limit: int = DEFAULT_LIMIT,
        teaser_count: int = DEFAULT_TEASER_COUNT,
    ) -> TapBoard:
        normalized_country = (target_country or "").strip().lower()
        filtered = self._filter_opportunities(opportunities or [], normalized_country)
        limited = filtered[: max(0, limit)]

        items = [
            self._build_item(
                opportunity=opportunity,
                target_country=normalized_country,
                paywall_tier=OpportunityTier.FREE_TEASER if index < teaser_count else OpportunityTier.PREMIUM,
            )
            for index, opportunity in enumerate(limited)
        ]

        return TapBoard(
            generated_at=datetime.utcnow().isoformat(),
            target_country=normalized_country,
            total_detected=len(filtered),
            teaser_count=max(0, teaser_count),
            items=items,
        )

    def _filter_opportunities(
        self,
        opportunities: list[ArbitrageOpportunity],
        target_country: str,
    ) -> list[ArbitrageOpportunity]:
        if not target_country:
            return sorted(opportunities, key=lambda item: item.priority, reverse=True)

        filtered = [
            item
            for item in opportunities
            if target_country in {country.lower() for country in item.target_countries}
        ]
        return sorted(filtered, key=lambda item: item.priority, reverse=True)

    def _build_item(
        self,
        *,
        opportunity: ArbitrageOpportunity,
        target_country: str,
        paywall_tier: OpportunityTier,
    ) -> TapBoardItem:
        window = self._estimate_publish_window(opportunity)
        platforms = self._recommend_platforms(opportunity)
        angle = self._recommend_angle(opportunity)
        return TapBoardItem(
            keyword=opportunity.keyword,
            source_country=opportunity.source_country,
            target_countries=list(opportunity.target_countries),
            viral_score=opportunity.viral_score,
            priority=opportunity.priority,
            time_gap_hours=opportunity.time_gap_hours,
            paywall_tier=paywall_tier,
            public_teaser=self._build_public_teaser(opportunity, target_country),
            recommended_platforms=platforms,
            recommended_angle=angle,
            execution_notes=self._build_execution_notes(opportunity, window, platforms),
            publish_window=window,
            revenue_play=self._build_revenue_play(opportunity),
        )

    def _estimate_publish_window(self, opportunity: ArbitrageOpportunity) -> PublishWindow:
        gap = max(0.0, opportunity.time_gap_hours)
        if gap <= 1.5:
            return PublishWindow(
                urgency_label="prep_now",
                opens_in_minutes=10,
                closes_in_minutes=90,
                rationale="Source market is moving now. Prepare the localized first wave immediately.",
            )
        if gap <= 8:
            return PublishWindow(
                urgency_label="first_wave",
                opens_in_minutes=0,
                closes_in_minutes=180,
                rationale="The gap is still fresh enough to win a first-mover slot in the target market.",
            )
        return PublishWindow(
            urgency_label="fast_follow",
            opens_in_minutes=0,
            closes_in_minutes=60,
            rationale="The window is narrowing. Package a fast follow-up angle instead of a cold open.",
        )

    def _recommend_platforms(self, opportunity: ArbitrageOpportunity) -> list[str]:
        if opportunity.viral_score >= 85:
            return ["x", "threads", "naver_blog"]
        if opportunity.time_gap_hours <= 4:
            return ["x", "threads"]
        return ["x"]

    def _recommend_angle(self, opportunity: ArbitrageOpportunity) -> str:
        if opportunity.time_gap_hours <= 3:
            return "Translate the signal before it mainstreams locally."
        if opportunity.viral_score >= 80:
            return "Reframe the overseas momentum as a local what-it-means-now story."
        return "Use a fast-follow explainer angle with explicit local context."

    def _build_public_teaser(self, opportunity: ArbitrageOpportunity, target_country: str) -> str:
        teaser_target = target_country.upper() if target_country else "TARGET"
        source = opportunity.source_country.upper()
        return (
            f"{source}에서 먼저 뜬 '{opportunity.keyword}' 신호. "
            f"{teaser_target} 시장에는 아직 빈 슬롯이 남아 있습니다."
        )

    def _build_execution_notes(
        self,
        opportunity: ArbitrageOpportunity,
        window: PublishWindow,
        platforms: list[str],
    ) -> list[str]:
        return [
            f"Prioritize {', '.join(platforms)} in the next {window.closes_in_minutes} minutes.",
            f"Localize the hook around a {opportunity.time_gap_hours:.1f}h information gap.",
            "Package a teaser headline for public reach and reserve the full playbook for premium users.",
        ]

    def _build_revenue_play(self, opportunity: ArbitrageOpportunity) -> RevenuePlay:
        if opportunity.viral_score >= 85:
            return RevenuePlay(
                playbook_type="sponsorship_ready",
                pricing_hint="premium_alert_bundle",
                cta_strategy="sell early access and execution templates",
                reasoning="High-signal arbitrage items are strong candidates for premium subscriptions or sponsor bundles.",
            )
        return RevenuePlay(
            playbook_type="lead_magnet",
            pricing_hint="teaser_to_email_capture",
            cta_strategy="use a teaser board to drive signups into the premium queue",
            reasoning="Mid-tier signals work well as top-of-funnel growth hooks before deeper monetization.",
        )


def required_tap_product_dependencies() -> list[str]:
    """Expose future dependency hints for install docs or setup UIs."""

    return list(FUTURE_LIBRARY_HINTS)


def _coerce_tier(value: Any) -> OpportunityTier:
    try:
        return OpportunityTier(str(value))
    except ValueError:
        return OpportunityTier.PREMIUM
