"""
shared.intelligence.topic_bridge

DailyNews 경제 브리프 토픽과 GetDayTrends 트렌드를 연결하는 크로스-파이프라인 인텔리전스 모듈.

주요 기능:
  1. DailyNews state DB에서 최근 보도된 카테고리/키워드 추출
  2. GetDayTrends scoring 시 경제 컨텍스트 가중치 계산
  3. 두 파이프라인 간 토픽 오버랩 분석
  4. 일치 카테고리에 가중치 boost (+10~+20%) 제공

사용법 (GetDayTrends analyzer.py 또는 prompt_builder.py에서):

    from shared.intelligence.topic_bridge import TopicBridge

    bridge = TopicBridge()
    boost = bridge.get_score_boost("삼성전자 반도체")
    # → {"boost": 15, "matched_categories": ["테크", "경제"], "reason": "..."}

    context = bridge.get_economic_context()
    # → {"hot_categories": [...], "hot_keywords": [...], "last_updated": "..."}
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


# ── 경로 설정 ─────────────────────────────────────────────────────────────────

_ROOT = Path(__file__).resolve().parents[3]
_DAILYNEWS_DB = (
    _ROOT / "automation" / "DailyNews" / "data" / "pipeline_state.db"
)
_GDT_DB = _ROOT / "automation" / "getdaytrends" / "data" / "getdaytrends.db"


# ── 카테고리 → 트렌드 키워드 매핑 ─────────────────────────────────────────────

# DailyNews 카테고리가 활성화됐을 때 GetDayTrends에서 boost할 토픽 관련어
_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "경제": ["금리", "환율", "주가", "코스피", "달러", "인플레", "GDP", "무역", "수출", "수입",
             "채권", "연준", "한국은행", "기준금리"],
    "테크": ["AI", "반도체", "엔비디아", "삼성", "애플", "구글", "메타", "오픈AI", "GPT",
             "스타트업", "유니콘", "IPO", "칩"],
    "정치": ["대통령", "국회", "선거", "정부", "법안", "탄핵", "외교", "정책", "여당", "야당"],
    "국제": ["미국", "중국", "일본", "유럽", "러시아", "전쟁", "무역분쟁", "제재", "G7", "G20"],
    "사회": ["부동산", "전세", "아파트", "청년", "출산율", "고령화", "복지", "의료", "교육"],
    "과학": ["우주", "NASA", "기후변화", "탄소", "에너지", "원전", "신재생", "배터리"],
}

# 카테고리별 기본 boost 포인트
_CATEGORY_BOOST: dict[str, int] = {
    "경제": 20,
    "테크": 18,
    "국제": 15,
    "정치": 12,
    "사회": 10,
    "과학": 10,
}


class TopicBridge:
    """
    DailyNews 경제 브리프와 GetDayTrends 트렌드 스코어링을 연결.

    - lookback_hours: DailyNews 브리프 조회 기간 (기본 24h)
    - cache_ttl_seconds: 인메모리 캐시 유효 시간 (기본 1800초)
    """

    def __init__(
        self,
        dailynews_db: str | None = None,
        gdt_db: str | None = None,
        lookback_hours: int = 24,
        cache_ttl_seconds: int = 1800,
    ) -> None:
        self._dn_db = dailynews_db or str(_DAILYNEWS_DB)
        self._gdt_db = gdt_db or str(_GDT_DB)
        self._lookback_hours = lookback_hours
        self._cache_ttl = cache_ttl_seconds
        self._cache: dict[str, Any] | None = None
        self._cache_at: datetime | None = None

    # ── 내부 DB 헬퍼 ───────────────────────────────────────────────────────────

    def _conn(self, path: str) -> sqlite3.Connection:
        c = sqlite3.connect(path)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        return c

    # ── DailyNews 데이터 로드 ──────────────────────────────────────────────────

    def _load_recent_briefs(self) -> list[dict]:
        """최근 lookback_hours 내 DailyNews 리포트에서 카테고리/요약 추출."""
        if not Path(self._dn_db).exists():
            return []

        since = (datetime.now(UTC) - timedelta(hours=self._lookback_hours)).isoformat()
        conn = self._conn(self._dn_db)
        try:
            rows = conn.execute(
                """
                SELECT category, summary_lines_json, insights_json, created_at
                FROM content_reports
                WHERE created_at >= ?
                ORDER BY created_at DESC
                """,
                (since,),
            ).fetchall()
        except sqlite3.OperationalError:
            # 테이블 구조 차이 방어
            rows = []
        finally:
            conn.close()

        briefs = []
        for r in rows:
            try:
                summary = json.loads(r["summary_lines_json"] or "[]")
                insights = json.loads(r["insights_json"] or "[]")
            except (json.JSONDecodeError, TypeError):
                summary, insights = [], []
            briefs.append({
                "category": r["category"],
                "summary": summary,
                "insights": insights,
                "created_at": r["created_at"],
            })
        return briefs

    def _build_cache(self) -> dict[str, Any]:
        """DailyNews 브리프에서 활성 카테고리 및 핫 키워드 구축."""
        briefs = self._load_recent_briefs()

        category_count: dict[str, int] = {}
        hot_keywords: list[str] = []

        for brief in briefs:
            cat = brief.get("category", "")
            if cat:
                category_count[cat] = category_count.get(cat, 0) + 1
            # 인사이트 텍스트에서 키워드 힌트 추출 (간단한 토큰화)
            for line in (brief.get("insights") or []):
                tokens = str(line).split()
                for tok in tokens:
                    tok = tok.strip(".,!?[]()\"'")
                    if len(tok) >= 2 and tok not in hot_keywords:
                        hot_keywords.append(tok)

        # 빈도 기준 정렬
        hot_cats = sorted(category_count, key=lambda c: category_count[c], reverse=True)

        return {
            "hot_categories": hot_cats[:6],
            "category_counts": category_count,
            "hot_keywords": hot_keywords[:40],
            "last_updated": datetime.now(UTC).isoformat(),
            "brief_count": len(briefs),
        }

    def _get_cache(self) -> dict[str, Any]:
        now = datetime.now(UTC)
        if (
            self._cache is None
            or self._cache_at is None
            or (now - self._cache_at).total_seconds() > self._cache_ttl
        ):
            self._cache = self._build_cache()
            self._cache_at = now
        return self._cache

    # ── 공개 API ───────────────────────────────────────────────────────────────

    def get_economic_context(self) -> dict[str, Any]:
        """
        현재 활성 경제 컨텍스트 반환.
        GetDayTrends context_collector.py 에서 주입용으로 사용.
        """
        return self._get_cache()

    def get_score_boost(self, keyword: str) -> dict[str, Any]:
        """
        키워드에 적용할 viral_potential boost 계산.

        Returns:
            {
                "boost": int,          # 0-20 포인트
                "matched_categories": list[str],
                "reason": str,
            }
        """
        if not keyword:
            return {"boost": 0, "matched_categories": [], "reason": "empty keyword"}

        cache = self._get_cache()
        hot_cats = set(cache.get("hot_categories", []))
        kw_lower = keyword.lower()

        matched: list[str] = []
        total_boost = 0

        for cat, keywords in _CATEGORY_KEYWORDS.items():
            if cat not in hot_cats:
                continue
            for kw in keywords:
                if kw.lower() in kw_lower or kw_lower in kw.lower():
                    if cat not in matched:
                        matched.append(cat)
                    cat_boost = _CATEGORY_BOOST.get(cat, 5)
                    total_boost = max(total_boost, cat_boost)
                    break

        if not matched:
            return {"boost": 0, "matched_categories": [], "reason": "카테고리 연관 없음"}

        reason = f"DailyNews 활성 카테고리 {matched} 연관 키워드"
        return {
            "boost": min(total_boost, 20),  # 최대 +20pt
            "matched_categories": matched,
            "reason": reason,
        }

    def get_weighted_categories(self) -> dict[str, float]:
        """
        현재 핫 카테고리별 가중치 반환 (합계 1.0).
        GetDayTrends 수집 필터링에 사용.
        """
        cache = self._get_cache()
        counts = cache.get("category_counts", {})
        total = sum(counts.values()) or 1
        return {cat: round(cnt / total, 4) for cat, cnt in counts.items()}

    def overlap_analysis(self, gdt_keywords: list[str]) -> dict[str, Any]:
        """
        GetDayTrends 트렌드 키워드 목록과 DailyNews 토픽 오버랩 분석.

        Args:
            gdt_keywords: 최근 수집된 GetDayTrends 트렌드 키워드 리스트

        Returns:
            {
                "overlap_count": int,
                "overlap_keywords": list[str],
                "overlap_rate": float,
                "top_synergy_category": str,
            }
        """
        cache = self._get_cache()
        dn_kw_set = {kw.lower() for kw in cache.get("hot_keywords", [])}

        overlap = [
            kw for kw in gdt_keywords
            if any(dn_kw in kw.lower() or kw.lower() in dn_kw for dn_kw in dn_kw_set)
        ]

        cat_hits: dict[str, int] = {}
        for kw in overlap:
            boost_info = self.get_score_boost(kw)
            for cat in boost_info.get("matched_categories", []):
                cat_hits[cat] = cat_hits.get(cat, 0) + 1

        top_cat = max(cat_hits, key=lambda c: cat_hits[c]) if cat_hits else ""

        return {
            "overlap_count": len(overlap),
            "overlap_keywords": overlap,
            "overlap_rate": round(len(overlap) / max(len(gdt_keywords), 1), 4),
            "top_synergy_category": top_cat,
        }

    def refresh(self) -> None:
        """캐시 강제 갱신."""
        self._cache = None
        self._cache_at = None
        self._get_cache()


# ── 편의 함수 ─────────────────────────────────────────────────────────────────

_default_bridge: TopicBridge | None = None


def get_default_bridge() -> TopicBridge:
    """싱글톤 기본 브리지 인스턴스."""
    global _default_bridge
    if _default_bridge is None:
        _default_bridge = TopicBridge()
    return _default_bridge


def get_score_boost(keyword: str) -> int:
    """편의 함수: 키워드에 대한 boost 포인트만 반환."""
    return get_default_bridge().get_score_boost(keyword)["boost"]


def get_economic_context() -> dict[str, Any]:
    """편의 함수: 현재 경제 컨텍스트 반환."""
    return get_default_bridge().get_economic_context()
