"""AI Convergence Guard v3 — Multi-source cross-verification + keyword lifecycle.

Extends v2 with:
1. Multi-source cross-verification: keywords appearing on 2+ platforms get extra boost
2. Keyword lifecycle tracking: emerging → peak → declining classification
3. Topic cluster detection: related AI keywords grouped into clusters
4. Confidence scoring: convergence confidence based on source diversity + volume
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from .ai_convergence_guard import AI_CONVERGENCE_THRESHOLD, AIConvergenceResult, _is_ai_trend

if TYPE_CHECKING:
    from storage.models import MergedTrendReport, PlatformTrend


class KeywordPhase(str, Enum):  # noqa: UP042
    """Keyword lifecycle phase."""

    EMERGING = "emerging"  # Low volume, few platforms
    GROWING = "growing"  # Rising volume, expanding platforms
    PEAK = "peak"  # High volume, many platforms
    DECLINING = "declining"  # Volume dropping, platforms shrinking


@dataclass
class KeywordLifecycle:
    """Lifecycle state for a single keyword."""

    keyword: str
    phase: KeywordPhase
    platform_count: int
    total_volume: int
    platforms: list[str] = field(default_factory=list)
    cluster: str = ""


@dataclass
class TopicCluster:
    """A group of related AI keywords."""

    name: str
    keywords: list[str]
    total_volume: int
    platform_count: int
    phase: KeywordPhase


@dataclass
class AIConvergenceResultV3(AIConvergenceResult):
    """Extended convergence result with v3 features."""

    cross_platform_hits: list[str] = field(default_factory=list)
    keyword_lifecycles: list[KeywordLifecycle] = field(default_factory=list)
    topic_clusters: list[TopicCluster] = field(default_factory=list)
    confidence_score: float = 0.0  # 0.0 ~ 1.0

    def summary(self) -> str:
        signal = "🔥 CONVERGENCE" if self.convergence_signal else "—"
        conf = f"[conf={self.confidence_score:.0%}]" if self.convergence_signal else ""
        cross = f" cross={len(self.cross_platform_hits)}" if self.cross_platform_hits else ""
        clusters = f" clusters={len(self.topic_clusters)}" if self.topic_clusters else ""
        return (
            f"AI Guard v3: {self.ai_trend_count}/{self.total_trend_count} "
            f"({self.ai_density:.0%}) {signal} {conf}{cross}{clusters}"
        )


# ── Topic Cluster Definitions ──
_TOPIC_CLUSTERS: dict[str, set[str]] = {
    "LLM/Foundation": {
        "llm",
        "gpt",
        "chatgpt",
        "claude",
        "gemini",
        "llama",
        "mistral",
        "deepseek",
        "transformer",
        "대규모 언어 모델",
        "large language model",
    },
    "Generative AI": {
        "sora",
        "midjourney",
        "dall-e",
        "stable diffusion",
        "diffusion",
        "생성ai",
        "생성형 ai",
    },
    "AI Agents": {
        "agent",
        "ai agent",
        "agentic",
        "mcp",
        "model context protocol",
        "copilot",
        "automation",
        "자동화",
    },
    "AI Safety/Regulation": {
        "ai 규제",
        "ai 법안",
        "ai 윤리",
        "ai safety",
        "ai alignment",
    },
    "ML Infrastructure": {
        "fine-tuning",
        "finetuning",
        "rag",
        "embedding",
        "벡터 검색",
        "vector search",
        "hugging face",
        "huggingface",
        "multimodal",
        "멀티모달",
    },
}


def _classify_phase(
    platform_count: int,
    total_volume: int,
) -> KeywordPhase:
    """Classify keyword lifecycle phase based on platform spread and volume."""
    if platform_count >= 3 and total_volume >= 50000:
        return KeywordPhase.PEAK
    if platform_count >= 2 and total_volume >= 10000:
        return KeywordPhase.GROWING
    if platform_count >= 2 or total_volume >= 5000:
        return KeywordPhase.EMERGING
    return KeywordPhase.EMERGING


def _find_cluster(keyword: str) -> str:
    """Find which topic cluster a keyword belongs to."""
    kw_lower = keyword.lower().strip()
    tokens = set(re.split(r"[\s_\-/]+", kw_lower))

    for cluster_name, cluster_keywords in _TOPIC_CLUSTERS.items():
        if kw_lower in cluster_keywords or tokens & cluster_keywords:
            return cluster_name
    return "Other AI"


def _calculate_confidence(
    ai_density: float,
    cross_platform_count: int,
    source_diversity: int,
    total_trends: int,
) -> float:
    """Calculate convergence confidence score (0.0 ~ 1.0).

    Factors:
    - AI density (weight 0.3)
    - Cross-platform keyword ratio (weight 0.3)
    - Source diversity (weight 0.2)
    - Volume adequacy (weight 0.2)
    """
    density_score = min(ai_density / 0.5, 1.0)
    cross_score = min(cross_platform_count / 5, 1.0)
    diversity_score = min(source_diversity / 4, 1.0)
    volume_score = min(total_trends / 20, 1.0)

    return 0.3 * density_score + 0.3 * cross_score + 0.2 * diversity_score + 0.2 * volume_score


def _collect_trends(report: MergedTrendReport) -> list[tuple[PlatformTrend, str]]:
    all_trends: list[tuple[PlatformTrend, str]] = []
    for platform_report in report.platform_reports:
        source = platform_report.platform
        for trend in platform_report.trends:
            all_trends.append((trend, source))
    return all_trends


def _collect_ai_trend_stats(
    all_trends: list[tuple[PlatformTrend, str]],
) -> tuple[list[tuple[PlatformTrend, str]], list[str], dict[str, set[str]], dict[str, int]]:
    ai_trends: list[tuple[PlatformTrend, str]] = []
    ai_keywords: list[str] = []
    keyword_platforms: dict[str, set[str]] = {}
    keyword_volumes: dict[str, int] = {}

    for trend, source in all_trends:
        if _is_ai_trend(trend):
            ai_trends.append((trend, source))
            keyword = trend.keyword.lower().strip()
            ai_keywords.append(trend.keyword)
            keyword_platforms.setdefault(keyword, set()).add(source)
            keyword_volumes[keyword] = keyword_volumes.get(keyword, 0) + (trend.volume or 0)

    return ai_trends, ai_keywords, keyword_platforms, keyword_volumes


def _cross_platform_hits(keyword_platforms: dict[str, set[str]]) -> list[str]:
    return [keyword for keyword, platforms in keyword_platforms.items() if len(platforms) >= 2]


def _build_lifecycles(
    keyword_platforms: dict[str, set[str]],
    keyword_volumes: dict[str, int],
) -> list[KeywordLifecycle]:
    lifecycles: list[KeywordLifecycle] = []
    for keyword, platforms in keyword_platforms.items():
        total_volume = keyword_volumes.get(keyword, 0)
        lifecycles.append(
            KeywordLifecycle(
                keyword=keyword,
                phase=_classify_phase(len(platforms), total_volume),
                platform_count=len(platforms),
                total_volume=total_volume,
                platforms=sorted(platforms),
                cluster=_find_cluster(keyword),
            )
        )
    return lifecycles


def _build_topic_clusters(lifecycles: list[KeywordLifecycle]) -> list[TopicCluster]:
    cluster_data: dict[str, dict] = {}
    for lifecycle in lifecycles:
        cluster_name = lifecycle.cluster
        if cluster_name not in cluster_data:
            cluster_data[cluster_name] = {"keywords": [], "volume": 0, "platforms": set()}
        cluster_data[cluster_name]["keywords"].append(lifecycle.keyword)
        cluster_data[cluster_name]["volume"] += lifecycle.total_volume
        cluster_data[cluster_name]["platforms"].update(lifecycle.platforms)

    topic_clusters = [
        TopicCluster(
            name=name,
            keywords=data["keywords"],
            total_volume=data["volume"],
            platform_count=len(data["platforms"]),
            phase=_classify_phase(len(data["platforms"]), data["volume"]),
        )
        for name, data in cluster_data.items()
    ]
    topic_clusters.sort(key=lambda cluster: cluster.total_volume, reverse=True)
    return topic_clusters


def _apply_boosts(
    ai_trends: list[tuple[PlatformTrend, str]],
    cross_platform_hits: list[str],
    *,
    cross_platform_boost: float,
    single_platform_boost: float,
) -> list[str]:
    boosted: list[str] = []
    for trend, _source in ai_trends:
        keyword = trend.keyword.lower().strip()
        is_cross_platform = keyword in cross_platform_hits
        boost = cross_platform_boost if is_cross_platform else single_platform_boost
        original = trend.volume
        trend.volume = int(trend.volume * boost) if trend.volume > 0 else 10
        tag = "⚡" if is_cross_platform else "↑"
        boosted.append(f"{tag} {trend.keyword} ({original}→{trend.volume})")
    return boosted


def _prepend_cross_platform_keywords(report: MergedTrendReport, cross_platform_hits: list[str]) -> None:
    existing = {keyword.lower() for keyword in report.cross_platform_keywords}
    for keyword in cross_platform_hits:
        if keyword not in existing:
            report.cross_platform_keywords.insert(0, keyword)
            existing.add(keyword)


def _prepend_convergence_insight(
    report: MergedTrendReport,
    *,
    density: float,
    confidence: float,
    cross_platform_count: int,
    topic_clusters: list[TopicCluster],
) -> None:
    cluster_summary = ", ".join(f"{cluster.name}({len(cluster.keywords)})" for cluster in topic_clusters[:3])
    signal_insight = (
        f"🔥 AI Convergence v3: {density:.0%} AI density "
        f"(conf={confidence:.0%}). "
        f"Cross-platform: {cross_platform_count} keywords. "
        f"Clusters: {cluster_summary}."
    )
    report.top_insights.insert(0, signal_insight)


def apply_ai_convergence_guard_v3(
    report: MergedTrendReport,
    *,
    threshold: float = AI_CONVERGENCE_THRESHOLD,
    cross_platform_boost: float = 2.0,
    single_platform_boost: float = 1.5,
) -> AIConvergenceResultV3:
    """v3: Multi-source cross-verification + keyword lifecycle + clustering.

    Improvements over v2:
    - Keywords on 2+ platforms get 2.0x boost (was 1.5x uniform)
    - Keywords on 1 platform get 1.5x boost
    - Lifecycle phases: emerging/growing/peak/declining
    - Topic clusters group related keywords
    - Confidence score reflects source diversity

    Args:
        report: Merged trend report from all platforms
        threshold: AI density threshold for convergence signal
        cross_platform_boost: Volume multiplier for multi-platform keywords
        single_platform_boost: Volume multiplier for single-platform keywords

    Returns:
        AIConvergenceResultV3 with enriched analysis
    """
    all_trends = _collect_trends(report)
    total = len(all_trends)
    if total == 0:
        return AIConvergenceResultV3(total_trend_count=0)

    ai_trends, ai_keywords, keyword_platforms, keyword_volumes = _collect_ai_trend_stats(all_trends)
    ai_count = len(ai_trends)
    density = ai_count / total
    convergence = density >= threshold
    cross_platform_hits = _cross_platform_hits(keyword_platforms)
    lifecycles = _build_lifecycles(keyword_platforms, keyword_volumes)
    topic_clusters = _build_topic_clusters(lifecycles)
    source_diversity = len({src for _, src in ai_trends})
    confidence = _calculate_confidence(
        density,
        len(cross_platform_hits),
        source_diversity,
        total,
    )

    boosted: list[str] = []
    if convergence:
        boosted = _apply_boosts(
            ai_trends,
            cross_platform_hits,
            cross_platform_boost=cross_platform_boost,
            single_platform_boost=single_platform_boost,
        )
        _prepend_cross_platform_keywords(report, cross_platform_hits)
        _prepend_convergence_insight(
            report,
            density=density,
            confidence=confidence,
            cross_platform_count=len(cross_platform_hits),
            topic_clusters=topic_clusters,
        )

    return AIConvergenceResultV3(
        ai_trend_count=ai_count,
        total_trend_count=total,
        ai_keywords_detected=ai_keywords,
        convergence_signal=convergence,
        boosted_keywords=boosted,
        cross_platform_hits=cross_platform_hits,
        keyword_lifecycles=lifecycles,
        topic_clusters=topic_clusters,
        confidence_score=confidence,
    )
