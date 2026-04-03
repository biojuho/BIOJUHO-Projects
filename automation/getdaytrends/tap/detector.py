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
    source_country: str         # 이미 트렌딩 중인 국가
    target_countries: list[str] # 아직 안 뜬 국가들
    viral_score: int = 0        # 원본 국가에서의 viral_potential
    time_gap_hours: float = 0.0 # source 국가에서 첫 감지 이후 경과 시간
    source_count: int = 1       # 원본에서 감지된 소스 개수
    priority: float = 0.0       # 선점 우선순위 (높을수록 좋음)
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
    """두 키워드가 같은 토픽인지 판별 (정규화 매치 + 부분 문자열)."""
    na, nb = _normalize_keyword(kw_a), _normalize_keyword(kw_b)
    if not na or not nb:
        return False
    # 정확 매치
    if na == nb:
        return True
    # 한쪽이 다른 쪽에 포함
    if na in nb or nb in na:
        return True
    # Jaccard character n-gram (bigram) similarity
    if len(na) >= 2 and len(nb) >= 2:
        bigrams_a = {na[i:i + 2] for i in range(len(na) - 1)}
        bigrams_b = {nb[i:i + 2] for i in range(len(nb) - 1)}
        if not bigrams_a or not bigrams_b:
            return False
        jaccard = len(bigrams_a & bigrams_b) / len(bigrams_a | bigrams_b)
        return jaccard >= threshold
    return False


# ══════════════════════════════════════════════════════
#  Core Detector
# ══════════════════════════════════════════════════════

class TrendArbitrageDetector:
    """교차국가 트렌드 시차 감지기."""

    # 기본 설정
    DEFAULT_LOOKBACK_HOURS = 12
    DEFAULT_MIN_VIRAL_SCORE = 60
    DEFAULT_SIMILARITY_THRESHOLD = 0.75
    MAX_OPPORTUNITIES = 10

    def __init__(self, conn, *, lookback_hours: int = 0, min_viral: int = 0):
        self._conn = conn
        self._lookback = lookback_hours or self.DEFAULT_LOOKBACK_HOURS
        self._min_viral = min_viral or self.DEFAULT_MIN_VIRAL_SCORE

    async def _fetch_recent_trends_by_country(self) -> dict[str, list[dict]]:
        """최근 N시간 이내 트렌드를 국가별로 그룹핑하여 반환."""
        cutoff = (datetime.now() - timedelta(hours=self._lookback)).isoformat()
        try:
            cursor = await self._conn.execute(
                "SELECT keyword, country, viral_potential, scored_at "
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

    async def _detect_impl(self, *, config=None) -> list[ArbitrageOpportunity]:
        by_country = await self._fetch_recent_trends_by_country()
        if len(by_country) < 2:
            log.debug(f"[TAP] 국가 수 부족 ({len(by_country)}개) → 차익거래 감지 생략")
            return []

        # 활성 국가 목록 (config에서 또는 DB에서 자동 추출)
        active_countries = list(by_country.keys())
        if config and hasattr(config, "countries") and config.countries:
            active_countries = [c.lower() for c in config.countries]

        opportunities: list[ArbitrageOpportunity] = []

        for source_country, source_trends in by_country.items():
            if source_country not in active_countries:
                continue

            # 이 국가의 키워드 집합
            source_keywords = {t["keyword"]: t for t in source_trends}

            for keyword, trend_data in source_keywords.items():
                # 다른 국가에서 이 키워드가 등장했는지 확인
                missing_in: list[str] = []

                for target_country in active_countries:
                    if target_country == source_country:
                        continue
                    target_trends = by_country.get(target_country, [])
                    target_keywords = [t["keyword"] for t in target_trends]

                    # 정확 매치 또는 유사 매치가 없으면 arbitrage 기회
                    found = any(
                        _is_same_topic(keyword, tk, self.DEFAULT_SIMILARITY_THRESHOLD)
                        for tk in target_keywords
                    )
                    if not found:
                        missing_in.append(target_country)

                if not missing_in:
                    continue

                # 시차 계산 (첫 감지 시각부터 현재까지)
                scored_at_str = trend_data.get("scored_at", "")
                time_gap = 0.0
                if scored_at_str:
                    try:
                        if "T" in scored_at_str:
                            scored_dt = datetime.fromisoformat(scored_at_str)
                        else:
                            scored_dt = datetime.strptime(scored_at_str, "%Y-%m-%d %H:%M:%S")
                        time_gap = (datetime.now() - scored_dt).total_seconds() / 3600
                    except (ValueError, TypeError):
                        pass

                viral = trend_data.get("viral_potential", 0)

                # Priority 계산:
                # - 바이럴 스코어가 높을수록 좋음
                # - 미감지 국가가 많을수록 좋음
                # - 시차가 적당히 있되 너무 오래되지 않으면 좋음 (sweet spot: 2-8h)
                time_factor = _time_priority_factor(time_gap)
                country_factor = len(missing_in) / max(len(active_countries) - 1, 1)
                priority = viral * 0.5 + time_factor * 30 + country_factor * 20

                opportunities.append(ArbitrageOpportunity(
                    keyword=keyword,
                    source_country=source_country,
                    target_countries=missing_in,
                    viral_score=viral,
                    time_gap_hours=round(time_gap, 1),
                    priority=round(priority, 1),
                ))

        # Deduplicate: 같은 키워드가 여러 source_country에서 잡히면 priority 최대값만 유지
        best: dict[str, ArbitrageOpportunity] = {}
        for opp in opportunities:
            nk = _normalize_keyword(opp.keyword)
            if nk not in best or opp.priority > best[nk].priority:
                best[nk] = opp

        sorted_opps = sorted(best.values(), key=lambda o: o.priority, reverse=True)
        return sorted_opps[:self.MAX_OPPORTUNITIES]


def _time_priority_factor(hours: float) -> float:
    """시차에 따른 우선도 계수 (0.0 ~ 1.0).

    sweet spot 2~8시간에 최대값, 너무 빠르거나(< 1h) 늦으면(> 12h) 감소.
    """
    if hours < 0.5:
        return 0.2  # 너무 빨리 잡힌 건 아직 불확실
    if hours <= 2:
        return 0.5 + (hours - 0.5) * 0.33  # 0.5h→0.2, 2h→1.0 선형 증가
    if hours <= 8:
        return 1.0  # sweet spot
    if hours <= 12:
        return 1.0 - (hours - 8) * 0.15  # 8h→1.0, 12h→0.4
    return max(0.1, 1.0 - (hours - 8) * 0.15)  # 12h 이후 점진 감소, 최저 0.1
