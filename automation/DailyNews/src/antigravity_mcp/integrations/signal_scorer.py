"""Cross-source signal scoring and arbitrage classification.

Takes raw TrendSignals from multiple sources and produces ScoredSignals
with composite scores, arbitrage type classifications, and recommended
actions for the DailyNews pipeline.

Scoring logic:
  - Multi-source overlap → multiplicative boost
  - High velocity → additional boost
  - Category affinity → alignment bonus
  - De-duplication via fuzzy keyword matching
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field

from antigravity_mcp.integrations.signal_collector import TrendSignal

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scored Signal Model
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ScoredSignal:
    """A trend signal after cross-source verification and scoring."""

    keyword: str
    composite_score: float  # 0.0~1.0, cross-verified
    sources: list[str]  # which sources detected this
    source_count: int = 0
    arbitrage_type: str = "noise"  # "early_wave" | "peak" | "noise" | "major"
    recommended_action: str = "skip"  # "draft_now" | "differentiate" | "skip" | "series"
    velocity: float = 0.0  # max velocity across sources
    category_hint: str = ""
    raw_signals: list[TrendSignal] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.source_count = len(self.sources)


# ---------------------------------------------------------------------------
# Fuzzy Keyword Normaliser
# ---------------------------------------------------------------------------


def _normalise_keyword(kw: str) -> str:
    """Normalise a keyword for fuzzy matching.

    - Strip whitespace, NFKC normalise
    - Lowercase
    - Remove common suffixes/particles
    """
    kw = unicodedata.normalize("NFKC", kw.strip())
    kw = kw.lower()
    # Remove Korean particles that don't change meaning
    kw = re.sub(r"[은는이가을를의로에서도와과]$", "", kw)
    # Remove trailing whitespace and punctuation
    kw = re.sub(r"[\s\-_.,!?]+$", "", kw)
    return kw


def _keywords_match(a: str, b: str) -> bool:
    """Check if two keywords are fuzzy-equivalent."""
    na, nb = _normalise_keyword(a), _normalise_keyword(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    # Substring containment (one within the other)
    if len(na) >= 3 and len(nb) >= 3 and (na in nb or nb in na):
        return True
    return False


# ---------------------------------------------------------------------------
# Signal Scorer
# ---------------------------------------------------------------------------


class SignalScorer:
    """Cross-source verification engine.

    Groups signals by fuzzy-matched keywords, then assigns composite
    scores and arbitrage classifications based on source overlap and
    velocity.
    """

    # Source weights — sources that are harder to game get more weight
    SOURCE_WEIGHTS: dict[str, float] = {
        "google_trends": 1.0,
        "getdaytrends": 0.9,
        "reddit": 0.8,
        "x_trending": 0.6,
    }

    # Multi-source multipliers
    MULTI_SOURCE_BOOST: dict[int, float] = {
        1: 1.0,
        2: 1.5,
        3: 2.0,
    }

    # Velocity threshold for "fast rise" bonus
    VELOCITY_THRESHOLD: float = 0.5

    # Minimum composite score to return
    MIN_SCORE: float = 0.1

    def __init__(
        self,
        *,
        target_categories: list[str] | None = None,
    ) -> None:
        self._target_categories = target_categories or []

    def score_signals(
        self,
        signals: list[TrendSignal],
        *,
        min_score: float | None = None,
    ) -> list[ScoredSignal]:
        """Score and classify all signals via cross-source verification.

        Args:
            signals: Raw signals from MultiSourceCollector.
            min_score: Minimum composite score to include (default: self.MIN_SCORE).

        Returns:
            list of ScoredSignal, sorted by composite_score descending.
        """
        if not signals:
            return []

        threshold = min_score if min_score is not None else self.MIN_SCORE

        # Step 1: Group by fuzzy-matched keyword
        groups = self._group_by_keyword(signals)

        # Step 2: Score each group
        scored: list[ScoredSignal] = []
        for canonical_kw, group_signals in groups.items():
            result = self._score_group(canonical_kw, group_signals)
            if result.composite_score >= threshold:
                scored.append(result)

        # Step 3: Sort by composite score
        scored.sort(key=lambda s: s.composite_score, reverse=True)

        logger.info(
            "SignalScorer: %d groups → %d above threshold (%.2f)",
            len(groups),
            len(scored),
            threshold,
        )
        return scored

    def _group_by_keyword(
        self,
        signals: list[TrendSignal],
    ) -> dict[str, list[TrendSignal]]:
        """Group signals by fuzzy-matched keyword. First seen keyword becomes canonical."""
        groups: dict[str, list[TrendSignal]] = {}
        canonical_map: dict[str, str] = {}  # normalised → canonical display keyword

        for signal in signals:
            norm = _normalise_keyword(signal.keyword)
            if not norm:
                continue

            # Find existing group
            matched_key: str | None = None
            for existing_norm in canonical_map:
                if _keywords_match(norm, existing_norm):
                    matched_key = existing_norm
                    break

            if matched_key is not None:
                canonical = canonical_map[matched_key]
                groups[canonical].append(signal)
            else:
                canonical_map[norm] = signal.keyword
                groups[signal.keyword] = [signal]

        return groups

    def _score_group(
        self,
        keyword: str,
        signals: list[TrendSignal],
    ) -> ScoredSignal:
        """Calculate composite score for a group of matching signals."""
        # Unique sources
        unique_sources = list({s.source for s in signals})
        source_count = len(unique_sources)

        # Weighted average base score
        total_weight = 0.0
        weighted_score = 0.0
        max_velocity = 0.0
        best_category = ""

        for signal in signals:
            w = self.SOURCE_WEIGHTS.get(signal.source, 0.5)
            weighted_score += signal.score * w
            total_weight += w
            max_velocity = max(max_velocity, signal.velocity)
            if signal.category_hint and not best_category:
                best_category = signal.category_hint

        base_score = weighted_score / max(total_weight, 0.01)

        # Multi-source boost
        multi_boost = self.MULTI_SOURCE_BOOST.get(
            min(source_count, 3), 2.0
        )
        boosted = base_score * multi_boost

        # Velocity bonus
        if max_velocity >= self.VELOCITY_THRESHOLD:
            boosted *= 1.3

        # Category affinity bonus
        if best_category and self._target_categories:
            if best_category in self._target_categories:
                boosted *= 1.2

        composite = min(1.0, round(boosted, 3))

        # Classify arbitrage type and action
        arbitrage_type, action = self._classify(
            source_count=source_count,
            unique_sources=unique_sources,
            composite=composite,
            velocity=max_velocity,
        )

        return ScoredSignal(
            keyword=keyword,
            composite_score=composite,
            sources=unique_sources,
            arbitrage_type=arbitrage_type,
            recommended_action=action,
            velocity=max_velocity,
            category_hint=best_category,
            raw_signals=signals,
        )

    def _classify(
        self,
        *,
        source_count: int,
        unique_sources: list[str],
        composite: float,
        velocity: float,
    ) -> tuple[str, str]:
        """Classify signal into arbitrage type and recommended action.

        Cross-Source Arbitrage Matrix:
        ┌────────────────────────────────┬──────────────┬───────────────────┐
        │ Condition                      │ Type         │ Action            │
        ├────────────────────────────────┼──────────────┼───────────────────┤
        │ 3+ sources + high velocity     │ major        │ series            │
        │ 2+ sources, X not dominant     │ early_wave   │ draft_now         │
        │ 2+ sources, all present        │ peak         │ differentiate     │
        │ 1 source only (X)              │ noise        │ skip              │
        │ 1 source (non-X), high score   │ early_wave   │ draft_now         │
        │ 1 source, low score            │ noise        │ skip              │
        └────────────────────────────────┴──────────────┴───────────────────┘
        """
        has_google = "google_trends" in unique_sources
        has_gdt = "getdaytrends" in unique_sources
        has_x = "x_trending" in unique_sources

        # 3+ sources with high velocity → major issue → series content
        if source_count >= 3 and velocity >= self.VELOCITY_THRESHOLD:
            return "major", "series"

        # 3+ sources → peak
        if source_count >= 3:
            return "peak", "differentiate"

        # 2 sources — check if X-only noise
        if source_count == 2:
            if has_x and not has_google and not has_gdt:
                return "noise", "skip"
            return "early_wave", "draft_now"

        # Single source
        if source_count == 1:
            if has_x:
                return "noise", "skip"
            if composite >= 0.6:
                return "early_wave", "draft_now"
            if composite >= 0.3:
                return "peak", "differentiate"
            return "noise", "skip"

        return "noise", "skip"
