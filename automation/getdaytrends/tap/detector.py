"""
TAP Detector — 교차국가 트렌드 시차(Arbitrage) 감지 엔진.

로직:
  1. DB에서 최근 N시간 이내의 트렌드를 국가별로 그룹핑
  2. 국가 A에 있고 국가 B에 없는 키워드를 식별 (정확 매치 + 유사도)
  3. 바이럴 스코어, 시차(시간), 소스 수로 priority 계산
  4. ArbitrageOpportunity 객체로 반환

Graceful Degradation:
  - 단일 국가 설정이면 빈 리스트 반환
  - DB 에러, 데이터 부족 시 빈 리스트 반환 (파이프라인 중단 없음)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from loguru import logger as log


@dataclass
class ArbitrageOpportunity:
    """하나의 교차국가 차익거래 기회를 나타냄."""

    keyword: str
    source_country: str  # 이미 트렌딩 중인 국가
    target_countries: list[str]  # 아직 안 뜬 국가들
    viral_score: int = 0  # 원본 국가에서의 viral_potential
    time_gap_hours: float = 0.0  # source 국가에서 첫 감지 이후 경과 시간
    source_count: int = 1  # 원본에서 감지된 소스 개수
    priority: float = 0.0  # 선점 우선순위 (높을수록 좋음)
    source_evidence: str = ""
    detected_at: datetime = field(default_factory=datetime.now)

    def to_prompt_hint(self) -> str:
        """LLM 프롬프트에 주입할 힌트 텍스트 생성."""
        targets = ", ".join(c.upper() for c in self.target_countries)
        return (
            f"[선점 기회] '{self.keyword}' — "
            f"{self.source_country.upper()}에서 viral {self.viral_score}점으로 트렌딩 중. "
            f"{targets}에서는 아직 미감지 (시차 {self.time_gap_hours:.1f}h). "
            f"선점 priority: {self.priority:.1f}"
        )


# ══════════════════════════════════════════════════════
#  Similarity helpers
# ══════════════════════════════════════════════════════


def _normalize_keyword(kw: str) -> str:
    """비교를 위한 키워드 정규화 (소문자, 공백 제거, ASCII-only stripped)."""
    return kw.strip().lower().replace(" ", "").replace("-", "").replace("_", "")


def _is_same_topic(kw_a: str, kw_b: str, threshold: float = 0.8) -> bool:
    """Return whether two normalized keywords describe the same topic."""
    na, nb = _normalize_keyword(kw_a), _normalize_keyword(kw_b)
    if not na or not nb:
        return False
    if _is_exact_or_contained_topic(na, nb):
        return True
    return _bigram_jaccard(na, nb) >= threshold


def _is_exact_or_contained_topic(kw_a: str, kw_b: str) -> bool:
    return kw_a == kw_b or kw_a in kw_b or kw_b in kw_a


def _bigram_jaccard(kw_a: str, kw_b: str) -> float:
    if len(kw_a) < 2 or len(kw_b) < 2:
        return 0.0
    bigrams_a = _bigrams(kw_a)
    bigrams_b = _bigrams(kw_b)
    if not bigrams_a or not bigrams_b:
        return 0.0
    return len(bigrams_a & bigrams_b) / len(bigrams_a | bigrams_b)


def _bigrams(value: str) -> set[str]:
    return {value[i : i + 2] for i in range(len(value) - 1)}


#  Core Detector
# ══════════════════════════════════════════════════════


class TrendArbitrageDetector:
    """교차국가 트렌드 시차 감지기."""

    # 기본 설정
    DEFAULT_LOOKBACK_HOURS = 12
    DEFAULT_MIN_VIRAL_SCORE = 60
    DEFAULT_SIMILARITY_THRESHOLD = 0.75
    MAX_OPPORTUNITIES = 10

    def __init__(self, conn, *, lookback_hours: int = 0, min_viral: int = 0) -> None:
        self._conn = conn
        self._lookback = lookback_hours or self.DEFAULT_LOOKBACK_HOURS
        self._min_viral = min_viral or self.DEFAULT_MIN_VIRAL_SCORE

    async def _fetch_recent_trends_by_country(self) -> dict[str, list[dict]]:
        """최근 N시간 이내 트렌드를 국가별로 그룹핑하여 반환."""
        cutoff = (datetime.now() - timedelta(hours=self._lookback)).isoformat()
        try:
            cursor = await self._conn.execute(
                "SELECT keyword, country, viral_potential, scored_at, top_insight "
                "FROM trends WHERE scored_at >= ? AND viral_potential >= ? "
                "ORDER BY viral_potential DESC",
                (cutoff, self._min_viral),
            )
            rows = await cursor.fetchall()
        except Exception as e:
            log.debug(f"[TAP] DB 조회 실패 (무시): {type(e).__name__}: {e}")
            return {}

        by_country: dict[str, list[dict]] = {}
        for row in rows:
            country = row["country"] or "unknown"
            by_country.setdefault(country, []).append(dict(row))
        return by_country

    async def detect(self, *, config=None) -> list[ArbitrageOpportunity]:
        """교차국가 차익거래 기회 감지.

        Args:
            config: AppConfig (countries 필드에서 활성 국가 목록 추출)

        Returns:
            ArbitrageOpportunity 리스트 (priority 내림차순)
        """
        try:
            return await self._detect_impl(config=config)
        except Exception as e:
            log.warning(f"[TAP] 감지 실패 (파이프라인 무중단): {type(e).__name__}: {e}")
            return []

    def _active_countries(self, by_country: dict[str, list[dict]], config=None) -> list[str]:
        if config and hasattr(config, "countries") and config.countries:
            return [country.lower() for country in config.countries]
        return list(by_country.keys())

    def _missing_target_countries(
        self,
        *,
        keyword: str,
        source_country: str,
        by_country: dict[str, list[dict]],
        active_countries: list[str],
    ) -> list[str]:
        missing_in: list[str] = []
        for target_country in active_countries:
            if target_country == source_country:
                continue
            target_keywords = [trend["keyword"] for trend in by_country.get(target_country, [])]
            found = any(
                _is_same_topic(keyword, target_keyword, self.DEFAULT_SIMILARITY_THRESHOLD)
                for target_keyword in target_keywords
            )
            if not found:
                missing_in.append(target_country)
        return missing_in

    def _trend_time_gap_hours(self, trend_data: dict) -> float:
        scored_at_str = trend_data.get("scored_at", "")
        if not scored_at_str:
            return 0.0
        try:
            if "T" in scored_at_str:
                scored_dt = datetime.fromisoformat(scored_at_str)
            else:
                scored_dt = datetime.strptime(scored_at_str, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return 0.0
        return (datetime.now() - scored_dt).total_seconds() / 3600

    def _opportunity_priority(self, *, viral: int, time_gap: float, missing_count: int, active_count: int) -> float:
        time_factor = _time_priority_factor(time_gap)
        country_factor = missing_count / max(active_count - 1, 1)
        return viral * 0.5 + time_factor * 30 + country_factor * 20

    def _build_opportunity(
        self,
        *,
        keyword: str,
        source_country: str,
        trend_data: dict,
        missing_in: list[str],
        active_countries: list[str],
    ) -> ArbitrageOpportunity:
        time_gap = self._trend_time_gap_hours(trend_data)
        viral = trend_data.get("viral_potential", 0)
        priority = self._opportunity_priority(
            viral=viral,
            time_gap=time_gap,
            missing_count=len(missing_in),
            active_count=len(active_countries),
        )
        return ArbitrageOpportunity(
            keyword=keyword,
            source_country=source_country,
            target_countries=missing_in,
            viral_score=viral,
            time_gap_hours=round(time_gap, 1),
            source_evidence=str(trend_data.get("top_insight", "") or "").strip(),
            priority=round(priority, 1),
        )

    def _opportunities_for_source(
        self,
        *,
        source_country: str,
        source_trends: list[dict],
        by_country: dict[str, list[dict]],
        active_countries: list[str],
    ) -> list[ArbitrageOpportunity]:
        if source_country not in active_countries:
            return []
        opportunities: list[ArbitrageOpportunity] = []
        for keyword, trend_data in {trend["keyword"]: trend for trend in source_trends}.items():
            missing_in = self._missing_target_countries(
                keyword=keyword,
                source_country=source_country,
                by_country=by_country,
                active_countries=active_countries,
            )
            if missing_in:
                opportunities.append(
                    self._build_opportunity(
                        keyword=keyword,
                        source_country=source_country,
                        trend_data=trend_data,
                        missing_in=missing_in,
                        active_countries=active_countries,
                    )
                )
        return opportunities

    def _dedupe_and_rank_opportunities(
        self, opportunities: list[ArbitrageOpportunity]
    ) -> list[ArbitrageOpportunity]:
        best: dict[str, ArbitrageOpportunity] = {}
        for opportunity in opportunities:
            normalized_keyword = _normalize_keyword(opportunity.keyword)
            if normalized_keyword not in best or opportunity.priority > best[normalized_keyword].priority:
                best[normalized_keyword] = opportunity
        return sorted(best.values(), key=lambda opportunity: opportunity.priority, reverse=True)[: self.MAX_OPPORTUNITIES]

    async def _detect_impl(self, *, config=None) -> list[ArbitrageOpportunity]:
        by_country = await self._fetch_recent_trends_by_country()
        if len(by_country) < 2:
            log.debug(f"[TAP] insufficient countries ({len(by_country)}); skipping arbitrage detection")
            return []

        active_countries = self._active_countries(by_country, config)
        opportunities: list[ArbitrageOpportunity] = []
        for source_country, source_trends in by_country.items():
            opportunities.extend(
                self._opportunities_for_source(
                    source_country=source_country,
                    source_trends=source_trends,
                    by_country=by_country,
                    active_countries=active_countries,
                )
            )

        return self._dedupe_and_rank_opportunities(opportunities)


def _time_priority_factor(hours: float) -> float:
    """시차에 따른 우선도 계수 (0.0 ~ 1.0).

    sweet spot 2~8시간에 최대값, 너무 빠르거나(< 1h) 늦으면(> 12h) 감소.
    """
    if hours < 0.5:
        return 0.2  # 너무 빨리 잡힌 건 아직 불확실
    if hours <= 2:
        return 0.5 + (hours - 0.5) * 0.33  # 0.5h→0.5, 2h→1.0 선형 증가
    if hours <= 8:
        return 1.0  # sweet spot
    if hours <= 12:
        return 1.0 - (hours - 8) * 0.15  # 8h→1.0, 12h→0.4
    return max(0.1, 1.0 - (hours - 8) * 0.15)  # 12h 이후 점진 감소, 최저 0.1
