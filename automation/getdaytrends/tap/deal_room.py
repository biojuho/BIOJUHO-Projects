"""
TAP Deal Room scaffolding.

This module productizes existing TAP signals into a monetizable surface:
1. public teaser cards for traffic,
2. premium execution bundles for paid conversion,
3. future checkout / CRM / lifecycle hooks.

The goal is to keep phase-1 implementation deterministic and dependency-light
while making room for future commercial integrations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

try:
    from .product_feed import OpportunityTier, TapBoard, TapBoardItem
except ImportError:
    from product_feed import OpportunityTier, TapBoard, TapBoardItem


FUTURE_TAP_DEAL_ROOM_DEPENDENCIES: tuple[str, ...] = (
    "stripe>=10.12.0",
    "jinja2>=3.1.4",
    "rapidfuzz>=3.9.0",
)


@dataclass(slots=True)
class DealRoomRequest:
    """Commercial contract for building a sellable TAP room."""

    target_country: str = ""
    limit: int = 10
    teaser_count: int = 3
    audience_segment: str = "creator"
    package_tier: str = "premium_alert_bundle"
    currency: str = "USD"
    include_public_teasers: bool = True
    include_checkout: bool = False
    checkout_provider: str = "stripe"
    capture_email: bool = True

    @property
    def normalized_target_country(self) -> str:
        return (self.target_country or "").strip().lower()


@dataclass(slots=True)
class DealRoomOffer:
    """One growth or revenue artifact derived from a TAP board item."""

    keyword: str
    tier: str
    package_tier: str
    teaser_headline: str
    teaser_body: str
    premium_title: str
    price_anchor: str
    price_value: float
    cta_label: str
    checkout_handle: str = ""
    bundle_outline: list[str] = field(default_factory=list)
    sponsor_fit: list[str] = field(default_factory=list)
    locked_sections: list[str] = field(default_factory=list)
    execution_deadline_minutes: int = 0
    funnel_stats: dict[str, Any] = field(default_factory=dict)
    learning_note: str = ""
    pricing_variant: str = "baseline_v1"
    pricing_context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "keyword": self.keyword,
            "tier": self.tier,
            "package_tier": self.package_tier,
            "teaser_headline": self.teaser_headline,
            "teaser_body": self.teaser_body,
            "premium_title": self.premium_title,
            "price_anchor": self.price_anchor,
            "price_value": self.price_value,
            "cta_label": self.cta_label,
            "checkout_handle": self.checkout_handle,
            "bundle_outline": list(self.bundle_outline),
            "sponsor_fit": list(self.sponsor_fit),
            "locked_sections": list(self.locked_sections),
            "execution_deadline_minutes": self.execution_deadline_minutes,
            "funnel_stats": dict(self.funnel_stats),
            "learning_note": self.learning_note,
            "pricing_variant": self.pricing_variant,
            "pricing_context": dict(self.pricing_context),
        }


@dataclass(slots=True)
class TapDealRoom:
    """API-friendly representation of a monetizable TAP room."""

    generated_at: str
    snapshot_id: str
    target_country: str
    audience_segment: str
    package_tier: str
    teaser_count: int
    total_detected: int
    offers: list[DealRoomOffer] = field(default_factory=list)
    future_dependencies: list[str] = field(default_factory=lambda: list(FUTURE_TAP_DEAL_ROOM_DEPENDENCIES))

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "snapshot_id": self.snapshot_id,
            "target_country": self.target_country,
            "audience_segment": self.audience_segment,
            "package_tier": self.package_tier,
            "teaser_count": self.teaser_count,
            "total_detected": self.total_detected,
            "offers": [offer.to_dict() for offer in self.offers],
            "future_dependencies": list(self.future_dependencies),
        }


class TapDealRoomBuilder:
    """Turns existing TAP board items into traffic + monetization packages."""

    DEFAULT_LOCKED_SECTIONS: tuple[str, ...] = (
        "localized_hook_pack",
        "publish_window",
        "platform_sequence",
        "sponsor_fit",
    )

    def build(
        self,
        board: TapBoard,
        *,
        request: DealRoomRequest | None = None,
        funnel_stats_map: dict[str, dict] | None = None,
        checkout_summary: dict[str, Any] | None = None,
    ) -> TapDealRoom:
        resolved = request or DealRoomRequest(
            target_country=board.target_country,
            teaser_count=board.teaser_count,
            limit=len(board.items),
        )

        projected_items = board.items[: max(0, resolved.limit)]
        if not resolved.include_public_teasers:
            projected_items = [
                item for item in projected_items if item.paywall_tier is not OpportunityTier.FREE_TEASER
            ]

        offers: list[DealRoomOffer] = []
        for item in projected_items:
            tier = "teaser" if item.paywall_tier is OpportunityTier.FREE_TEASER else "premium"
            stats_key = f"{self._stats_keyword(item.keyword)}::{tier}"
            stats = dict((funnel_stats_map or {}).get(stats_key, {}))
            offer = self._build_offer(
                item,
                request=resolved,
                funnel_stats=stats,
                checkout_summary=checkout_summary or {},
            )
            if stats:
                offer.funnel_stats = stats
            offer.learning_note = self._learning_note(stats, offer.pricing_context)
            offers.append(offer)

        return TapDealRoom(
            generated_at=datetime.utcnow().isoformat(),
            snapshot_id=board.snapshot_id,
            target_country=resolved.normalized_target_country or board.target_country,
            audience_segment=resolved.audience_segment,
            package_tier=resolved.package_tier,
            teaser_count=resolved.teaser_count,
            total_detected=board.total_detected,
            offers=offers,
        )

    def _build_offer(
        self,
        item: TapBoardItem,
        *,
        request: DealRoomRequest,
        funnel_stats: dict[str, Any] | None = None,
        checkout_summary: dict[str, Any] | None = None,
    ) -> DealRoomOffer:
        tier = "teaser" if item.paywall_tier is OpportunityTier.FREE_TEASER else "premium"
        package_tier = self._package_tier(item, request)
        pricing = self._price_decision(
            item,
            request.currency,
            package_tier,
            request=request,
            funnel_stats=funnel_stats or {},
            checkout_summary=checkout_summary or {},
        )
        cta_label = self._cta_label(tier, request)
        checkout_handle = ""
        if request.include_checkout:
            checkout_handle = self._checkout_handle(item, request, package_tier)

        bundle_outline = self._bundle_outline(item)
        sponsor_fit = self._sponsor_fit(item, request.audience_segment)
        deadline_minutes = 0
        if item.publish_window:
            deadline_minutes = max(0, item.publish_window.closes_in_minutes)

        return DealRoomOffer(
            keyword=item.keyword,
            tier=tier,
            package_tier=package_tier,
            teaser_headline=self._teaser_headline(item),
            teaser_body=self._teaser_body(item),
            premium_title=self._premium_title(item, package_tier),
            price_anchor=pricing["price_anchor"],
            price_value=float(pricing["price_value"]),
            cta_label=cta_label,
            checkout_handle=checkout_handle,
            bundle_outline=bundle_outline,
            sponsor_fit=sponsor_fit,
            locked_sections=list(self.DEFAULT_LOCKED_SECTIONS),
            execution_deadline_minutes=deadline_minutes,
            pricing_variant=str(pricing["pricing_variant"]),
            pricing_context=dict(pricing["pricing_context"]),
        )

    def _stats_keyword(self, keyword: str) -> str:
        return "".join(ch for ch in (keyword or "").strip().lower() if ch.isalnum())

    def _teaser_headline(self, item: TapBoardItem) -> str:
        route = f"{item.source_country.upper()} -> {','.join(country.upper() for country in item.target_countries[:2])}"
        return f"{route} first-mover signal: {item.keyword}"

    def _teaser_body(self, item: TapBoardItem) -> str:
        return item.public_teaser or (
            f"'{item.keyword}' is already moving abroad. "
            "Unlock the local execution playbook before it turns obvious."
        )

    def _premium_title(self, item: TapBoardItem, package_tier: str) -> str:
        title = package_tier.replace("_", " ").strip() or "execution bundle"
        return f"{item.keyword} {title}"

    def _base_price(self, item: TapBoardItem, package_tier: str) -> float:
        if "sponsor" in package_tier:
            return 299.0
        if "email_capture" in package_tier:
            return 29.0
        if "lead_magnet" in package_tier:
            return 39.0
        if item.viral_score >= 90:
            return 99.0
        if item.viral_score >= 80:
            return 49.0
        return 19.0

    def _price_anchor(self, price_value: float, currency: str) -> str:
        symbol = "$" if currency.upper() == "USD" else currency.upper()
        return f"{symbol}{int(round(price_value))}"

    def _snap_price(self, raw_price: float) -> float:
        ladder = [19, 29, 39, 49, 59, 79, 99, 129, 149, 199, 249, 299, 399]
        bounded = max(ladder[0], min(raw_price, ladder[-1]))
        return float(min(ladder, key=lambda anchor: abs(anchor - bounded)))

    def _audience_multiplier(self, audience_segment: str) -> float:
        segment = (audience_segment or "").strip().lower()
        return {
            "creator": 1.0,
            "marketer": 1.1,
            "brand": 1.2,
            "agency": 1.35,
            "investor": 1.4,
        }.get(segment, 1.0)

    def _country_multiplier(self, country: str) -> float:
        normalized = (country or "").strip().lower()
        return {
            "united-states": 1.0,
            "united-kingdom": 1.1,
            "japan": 1.1,
            "korea": 0.95,
            "india": 0.8,
            "brazil": 0.9,
        }.get(normalized, 1.0)

    def _price_decision(
        self,
        item: TapBoardItem,
        currency: str,
        package_tier: str,
        *,
        request: DealRoomRequest,
        funnel_stats: dict[str, Any],
        checkout_summary: dict[str, Any],
    ) -> dict[str, Any]:
        base_price = self._base_price(item, package_tier)
        audience_multiplier = self._audience_multiplier(request.audience_segment)
        country_multiplier = self._country_multiplier(request.normalized_target_country)
        experiment_multiplier = 1.0
        experiment_strategy = "baseline"

        views = int(funnel_stats.get("views", 0) or 0)
        clicks = int(funnel_stats.get("clicks", 0) or 0)
        purchases = int(funnel_stats.get("purchases", 0) or 0)
        purchase_rate = float(funnel_stats.get("purchase_rate", 0.0) or 0.0)
        checkout_completion_rate = float((checkout_summary.get("totals") or {}).get("completion_rate", 0.0) or 0.0)

        if clicks >= 5 and purchases == 0:
            experiment_multiplier = 0.85
            experiment_strategy = "recovery"
        elif checkout_completion_rate >= 0.45 and (purchase_rate >= 0.2 or purchases >= 2):
            experiment_multiplier = 1.15
            experiment_strategy = "expansion"
        elif checkout_completion_rate <= 0.18 and clicks >= 3:
            experiment_multiplier = 0.8
            experiment_strategy = "friction_reset"
        elif checkout_completion_rate >= 0.35 and views >= 20:
            experiment_multiplier = 1.08
            experiment_strategy = "confidence_lift"

        raw_price = base_price * audience_multiplier * country_multiplier * experiment_multiplier
        snapped_price = self._snap_price(raw_price)
        normalized_country = (request.normalized_target_country or "global").replace("-", "_")
        normalized_segment = (request.audience_segment or "creator").strip().lower() or "creator"
        normalized_package = package_tier.replace("-", "_")
        pricing_variant = f"{normalized_country}__{normalized_segment}__{normalized_package}__{experiment_strategy}_v1"

        pricing_context = {
            "base_price": base_price,
            "audience_multiplier": audience_multiplier,
            "country_multiplier": country_multiplier,
            "experiment_multiplier": experiment_multiplier,
            "experiment_strategy": experiment_strategy,
            "checkout_completion_rate": checkout_completion_rate,
            "offer_purchase_rate": purchase_rate,
            "views": views,
            "clicks": clicks,
            "purchases": purchases,
        }
        return {
            "price_value": snapped_price,
            "price_anchor": self._price_anchor(snapped_price, currency),
            "pricing_variant": pricing_variant,
            "pricing_context": pricing_context,
        }

    def _cta_label(self, tier: str, request: DealRoomRequest) -> str:
        if tier == "teaser":
            return "Unlock premium playbook" if request.capture_email else "View full bundle"
        return "Buy now" if request.include_checkout else "Reserve access"

    def _checkout_handle(self, item: TapBoardItem, request: DealRoomRequest, package_tier: str) -> str:
        target = request.normalized_target_country or "global"
        return f"{request.checkout_provider}:{package_tier}:{target}:{item.keyword}"

    def _package_tier(self, item: TapBoardItem, request: DealRoomRequest) -> str:
        if request.package_tier and request.package_tier != "premium_alert_bundle":
            return request.package_tier
        if item.revenue_play and item.revenue_play.pricing_hint:
            return item.revenue_play.pricing_hint
        return request.package_tier

    def _bundle_outline(self, item: TapBoardItem) -> list[str]:
        outline = [
            f"Localized hook: {item.recommended_angle or 'translate the overseas signal into a local story'}",
            f"Platform sequence: {', '.join(item.recommended_platforms or ['x'])}",
            f"Execution notes: {' | '.join(item.execution_notes[:2])}",
        ]
        if item.publish_window:
            outline.append(
                "Publish window: "
                f"{item.publish_window.opens_in_minutes}-{item.publish_window.closes_in_minutes} minutes"
            )
        if item.revenue_play:
            outline.append(f"Commercial angle: {item.revenue_play.playbook_type}")
        return outline

    def _sponsor_fit(self, item: TapBoardItem, audience_segment: str) -> list[str]:
        base = [audience_segment, "tooling", "media-buy"]
        if item.viral_score >= 85:
            base.append("enterprise sponsor")
        if "naver_blog" in (item.recommended_platforms or []):
            base.append("seo partner")
        return base

    def _learning_note(self, stats: dict[str, Any], pricing_context: dict[str, Any] | None = None) -> str:
        notes: list[str] = []
        views = int(stats.get("views", 0) or 0)
        clicks = int(stats.get("clicks", 0) or 0)
        purchases = int(stats.get("purchases", 0) or 0)
        ctr = float(stats.get("ctr", 0.0) or 0.0)
        purchase_rate = float(stats.get("purchase_rate", 0.0) or 0.0)
        if purchases >= 3 and purchase_rate >= 0.2:
            notes.append("High-intent bundle. Keep the offer structure stable.")
        elif clicks >= 5 and purchases == 0:
            notes.append("Interest exists but conversion is weak. Test pricing or checkout friction.")
        elif views >= 20 and ctr < 0.05:
            notes.append("Teaser underperforms. Refresh the top-line hook.")
        elif ctr >= 0.15:
            notes.append("Hook is resonating. Drive more exposure into this lane.")

        strategy = str((pricing_context or {}).get("experiment_strategy", "") or "")
        if strategy == "recovery":
            notes.append("Price is running in recovery mode to reduce checkout drop-off.")
        elif strategy == "expansion":
            notes.append("Price is holding a premium lift because recent completion is strong.")
        elif strategy == "friction_reset":
            notes.append("Price is temporarily softened to test checkout friction reset.")
        elif strategy == "confidence_lift":
            notes.append("Price is slightly elevated on a strong segment close rate.")
        return " ".join(notes).strip()


def required_tap_deal_room_dependencies() -> list[str]:
    """Dependency hints for future monetization activation."""

    return list(FUTURE_TAP_DEAL_ROOM_DEPENDENCIES)


async def build_tap_deal_room_snapshot(
    conn,
    config,
    request: DealRoomRequest | None = None,
) -> TapDealRoom:
    """Build a deal-room payload from the freshest TAP board snapshot."""

    try:
        from .service import TapBoardRequest, build_tap_board_snapshot
    except ImportError:
        from service import TapBoardRequest, build_tap_board_snapshot

    try:
        from ..db import get_tap_checkout_session_summary, get_tap_deal_room_offer_stats
    except ImportError:
        from db import get_tap_checkout_session_summary, get_tap_deal_room_offer_stats

    resolved = request or DealRoomRequest()
    board = await build_tap_board_snapshot(
        conn,
        config,
        TapBoardRequest(
            target_country=resolved.normalized_target_country or getattr(config, "country", ""),
            limit=resolved.limit,
            teaser_count=resolved.teaser_count,
            snapshot_source="tap_deal_room",
        ),
    )
    try:
        stats_map = await get_tap_deal_room_offer_stats(
            conn,
            days=30,
            target_country=resolved.normalized_target_country or getattr(config, "country", ""),
            audience_segment=resolved.audience_segment,
            package_tier=resolved.package_tier,
        )
    except Exception:
        stats_map = {}
    try:
        checkout_summary = await get_tap_checkout_session_summary(
            conn,
            days=30,
            target_country=resolved.normalized_target_country or getattr(config, "country", ""),
            audience_segment=resolved.audience_segment,
            package_tier=resolved.package_tier,
            limit=10,
        )
    except Exception:
        checkout_summary = {}
    return TapDealRoomBuilder().build(
        board,
        request=resolved,
        funnel_stats_map=stats_map,
        checkout_summary=checkout_summary,
    )
