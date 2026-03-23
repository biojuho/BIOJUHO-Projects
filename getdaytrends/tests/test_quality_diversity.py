"""
getdaytrends v6.0/v6.1 - 품질 피드백 + 카테고리 다양성 + 최신성 검증 테스트
_ensure_quality_and_diversity 알고리즘 검증 + content_feedback DB 테스트.
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


from config import AppConfig
from db import get_connection, init_db, record_content_feedback
from models import MultiSourceContext, ScoredTrend, TrendSource


# ══════════════════════════════════════════════════════
#  Fixtures
# ══════════════════════════════════════════════════════


@pytest.fixture
def config() -> AppConfig:
    cfg = AppConfig()
    cfg.min_viral_score = 60
    cfg.min_article_count = 5
    cfg.max_same_category = 2
    cfg.enable_sentiment_filter = True
    cfg.enable_quality_feedback = True
    cfg.quality_feedback_min_score = 50
    cfg.freshness_penalty_stale = 0.85
    cfg.freshness_penalty_expired = 0.7
    cfg.exclude_categories = []  # 기존 테스트는 제외 없이 실행
    return cfg


@pytest.fixture
async def conn():
    """인메모리 SQLite 연결 (테스트 격리)."""
    db = await get_connection(":memory:")
    await init_db(db)
    yield db
    await db.close()


def _make_trend(
    keyword: str,
    viral: int = 75,
    category: str = "테크",
    safety: bool = False,
    content_age_hours: float = 0.0,
    freshness_grade: str = "unknown",
) -> ScoredTrend:
    return ScoredTrend(
        keyword=keyword,
        rank=1,
        viral_potential=viral,
        trend_acceleration="+5%",
        top_insight="테스트 인사이트",
        suggested_angles=["앵글1"],
        best_hook_starter="최고의 훅",
        category=category,
        context=MultiSourceContext(),
        safety_flag=safety,
        sentiment="neutral",
        content_age_hours=content_age_hours,
        freshness_grade=freshness_grade,
    )


# ══════════════════════════════════════════════════════
#  _ensure_quality_and_diversity 테스트
# ══════════════════════════════════════════════════════


def test_ensure_min_article_count(config):
    """바이럴 점수 낮은 트렌드들 → 최소 5개 보장."""
    from core.pipeline import _ensure_quality_and_diversity

    trends = [
        _make_trend("트렌드1", viral=55, category="연예"),
        _make_trend("트렌드2", viral=50, category="스포츠"),
        _make_trend("트렌드3", viral=45, category="테크"),
        _make_trend("트렌드4", viral=40, category="정치"),
        _make_trend("트렌드5", viral=38, category="경제"),
        _make_trend("트렌드6", viral=37, category="사회"),
        _make_trend("트렌드7", viral=36, category="과학"),
    ]

    result = _ensure_quality_and_diversity(trends, config)
    # floor_score = 60 * 0.75 = 45, viral 45 이상만 보충 가능
    # 트렌드1(55), 트렌드2(50), 트렌드3(45)가 floor 이상
    assert len(result) >= 3
    assert len(result) <= 5


def test_ensure_min_with_sufficient_trends(config):
    """충분한 바이럴 점수 트렌드 → 정상 필터링."""
    from core.pipeline import _ensure_quality_and_diversity

    trends = [
        _make_trend("높은1", viral=90, category="테크"),
        _make_trend("높은2", viral=85, category="연예"),
        _make_trend("높은3", viral=80, category="스포츠"),
        _make_trend("높은4", viral=75, category="정치"),
        _make_trend("낮은1", viral=29, category="기타"),  # floor_score(30) 미만
    ]

    result = _ensure_quality_and_diversity(trends, config)
    assert len(result) == 4  # 29점은 floor_score(45) 미만으로 여전히 제외


def test_category_diversity(config):
    """동일 카테고리 5개 → 다른 카테고리 포함 + max_same 제한."""
    from core.pipeline import _ensure_quality_and_diversity

    trends = [
        _make_trend("테크1", viral=90, category="테크"),
        _make_trend("테크2", viral=85, category="테크"),
        _make_trend("테크3", viral=80, category="테크"),
        _make_trend("테크4", viral=75, category="테크"),
        _make_trend("연예1", viral=70, category="연예"),
        _make_trend("스포츠1", viral=68, category="스포츠"),
        _make_trend("경제1", viral=65, category="경제"),
        _make_trend("사회1", viral=63, category="사회"),
    ]

    result = _ensure_quality_and_diversity(trends, config)
    tech_count = sum(1 for t in result if t.category == "테크")
    assert tech_count <= 2  # max_same_category=2
    ent_count = sum(1 for t in result if t.category == "연예")
    assert ent_count >= 1


def test_max_same_category_limit(config):
    """같은 카테고리 초과 시 차순위로 대체."""
    from core.pipeline import _ensure_quality_and_diversity

    config.max_same_category = 1

    trends = [
        _make_trend("정치1", viral=95, category="정치"),
        _make_trend("정치2", viral=90, category="정치"),
        _make_trend("경제1", viral=85, category="경제"),
        _make_trend("테크1", viral=80, category="테크"),
        _make_trend("연예1", viral=78, category="연예"),
        _make_trend("스포츠1", viral=75, category="스포츠"),
        _make_trend("사회1", viral=72, category="사회"),
    ]

    result = _ensure_quality_and_diversity(trends, config)
    cat_counts = {}
    for t in result:
        cat_counts[t.category] = cat_counts.get(t.category, 0) + 1
    for count in cat_counts.values():
        assert count <= 1


def test_safety_flag_excluded(config):
    """safety_flag=True 트렌드는 다양성 선택에서 제외."""
    from core.pipeline import _ensure_quality_and_diversity

    trends = [
        _make_trend("위험트렌드", viral=95, category="사회", safety=True),
        _make_trend("안전1", viral=70, category="테크"),
        _make_trend("안전2", viral=65, category="연예"),
        _make_trend("안전3", viral=60, category="스포츠"),
    ]

    result = _ensure_quality_and_diversity(trends, config)
    assert "위험트렌드" not in [t.keyword for t in result]
    assert len(result) == 3


def test_empty_trends(config):
    """빈 트렌드 목록 → 빈 결과."""
    from core.pipeline import _ensure_quality_and_diversity

    result = _ensure_quality_and_diversity([], config)
    assert result == []


def test_diversity_preserves_order(config):
    """결과는 바이럴 점수 내림차순으로 정렬."""
    from core.pipeline import _ensure_quality_and_diversity

    trends = [
        _make_trend("낮음", viral=65, category="연예"),
        _make_trend("높음", viral=90, category="테크"),
        _make_trend("중간", viral=75, category="스포츠"),
    ]

    config.exclude_categories = []  # fixture에서 이미 설정, 명시성을 위해 유지
    result = _ensure_quality_and_diversity(trends, config)
    scores = [t.viral_potential for t in result]
    assert scores == sorted(scores, reverse=True)


def test_exclude_categories(config):
    """정치·연예 카테고리 트렌드가 결과에서 제외."""
    from core.pipeline import _ensure_quality_and_diversity

    config.exclude_categories = ["정치", "연예"]

    trends = [
        _make_trend("테크뉴스", viral=90, category="테크"),
        _make_trend("정치이슈", viral=95, category="정치"),
        _make_trend("아이돌컴백", viral=88, category="연예"),
        _make_trend("스포츠", viral=80, category="스포츠"),
        _make_trend("경제뉴스", viral=70, category="경제"),
    ]

    result = _ensure_quality_and_diversity(trends, config)
    result_keywords = [t.keyword for t in result]
    assert "정치이슈" not in result_keywords
    assert "아이돌컴백" not in result_keywords
    assert "테크뉴스" in result_keywords
    assert "스포츠" in result_keywords


def test_exclude_categories_empty(config):
    """빈 제외 목록이면 모든 카테고리 통과."""
    from core.pipeline import _ensure_quality_and_diversity

    config.exclude_categories = []

    trends = [
        _make_trend("정치뉴스", viral=90, category="정치"),
        _make_trend("연예뉴스", viral=85, category="연예"),
        _make_trend("테크뉴스", viral=80, category="테크"),
    ]

    result = _ensure_quality_and_diversity(trends, config)
    assert len(result) == 3


def test_exclude_categories_dynamic_min_count(config):
    """카테고리 제외 후 남은 트렌드가 min_count 미만이면 동적 축소."""
    from core.pipeline import _ensure_quality_and_diversity

    config.exclude_categories = ["정치", "연예"]
    config.min_article_count = 5

    trends = [
        _make_trend("테크뉴스", viral=90, category="테크"),
        _make_trend("정치이슈", viral=95, category="정치"),
        _make_trend("아이돌", viral=88, category="연예"),
        _make_trend("스포츠", viral=80, category="스포츠"),
    ]

    # 정치+연예 제외 → 2개 남음 → min_count=min(5,2)=2 → 2개 정상 반환
    result = _ensure_quality_and_diversity(trends, config)
    assert len(result) == 2
    result_keywords = [t.keyword for t in result]
    assert "정치이슈" not in result_keywords
    assert "아이돌" not in result_keywords
    assert "테크뉴스" in result_keywords
    assert "스포츠" in result_keywords


def test_exclude_all_leaves_empty(config):
    """모든 트렌드가 제외 카테고리면 빈 결과 (zero-content prevention 비활성화 시)."""
    from core.pipeline import _ensure_quality_and_diversity

    config.exclude_categories = ["정치", "연예"]
    config.enable_zero_content_prevention = False  # [v15.0] 명시적 비활성화

    trends = [
        _make_trend("정치1", viral=95, category="정치"),
        _make_trend("연예1", viral=90, category="연예"),
    ]

    result = _ensure_quality_and_diversity(trends, config)
    assert result == []


def test_publishable_false_excluded(config):
    """[v13.0] publishable=false 트렌드는 결과에서 제외."""
    from core.pipeline import _ensure_quality_and_diversity

    trends = [
        _make_trend("정상트렌드", viral=90, category="테크"),
        _make_trend("문장조각", viral=85, category="기타"),
        _make_trend("오타키워드", viral=80, category="연예"),
    ]
    # publishable=false 설정
    trends[1].publishable = False
    trends[1].publishability_reason = "문장 조각"

    result = _ensure_quality_and_diversity(trends, config)
    result_keywords = [t.keyword for t in result]
    assert "문장조각" not in result_keywords
    assert "정상트렌드" in result_keywords
    assert "오타키워드" in result_keywords


# ══════════════════════════════════════════════════════
#  [v6.1] 시간 감쇠 신선도 점수 테스트
# ══════════════════════════════════════════════════════


def test_compute_freshness_score_brand_new():
    """0시간 경과 (최신) → 20점."""
    from analyzer import _compute_freshness_score

    assert _compute_freshness_score(0.0, is_new=True) == 20.0
    assert _compute_freshness_score(0.5) == 20.0  # 30분 → 20점


def test_compute_freshness_score_1h():
    """1시간 경과 → 20점."""
    from analyzer import _compute_freshness_score

    assert _compute_freshness_score(1.0) == 20.0


def test_compute_freshness_score_3h():
    """3시간 경과 → 15점."""
    from analyzer import _compute_freshness_score

    score = _compute_freshness_score(3.0)
    assert abs(score - 15.0) < 0.5


def test_compute_freshness_score_6h():
    """6시간 경과 → 10점."""
    from analyzer import _compute_freshness_score

    score = _compute_freshness_score(6.0)
    assert abs(score - 10.0) < 0.5


def test_compute_freshness_score_12h():
    """12시간 경과 → 5점."""
    from analyzer import _compute_freshness_score

    score = _compute_freshness_score(12.0)
    assert abs(score - 5.0) < 0.5


def test_compute_freshness_score_24h():
    """24시간 경과 → 0점."""
    from analyzer import _compute_freshness_score

    score = _compute_freshness_score(24.0)
    assert score <= 1.0  # 거의 0


def test_compute_freshness_score_fallback():
    """content_age=0 + is_new=False → 10점 (바이너리 폴백)."""
    from analyzer import _compute_freshness_score

    assert _compute_freshness_score(0.0, is_new=False) == 10.0


# ══════════════════════════════════════════════════════
#  [v6.1] 최신성 등급 + 패널티 테스트
# ══════════════════════════════════════════════════════


def test_freshness_grade_assignment(config):
    """content_age에 따른 freshness_grade 부여 검증."""
    from core.pipeline import _ensure_quality_and_diversity

    trends = [
        _make_trend("최신", viral=90, category="테크", content_age_hours=1.0),
        _make_trend("준최신", viral=85, category="연예", content_age_hours=8.0),
        _make_trend("낙후", viral=80, category="스포츠", content_age_hours=15.0),
        _make_trend("만료", viral=90, category="정치", content_age_hours=30.0),
    ]

    result = _ensure_quality_and_diversity(trends, config)
    grade_map = {t.keyword: t.freshness_grade for t in result}

    assert grade_map["최신"] == "fresh"       # 0~6h
    assert grade_map["준최신"] == "recent"     # 6~12h
    assert grade_map["낙후"] == "stale"        # 12~24h
    assert grade_map["만료"] == "expired"      # 24h+


def test_expired_trend_penalty(config):
    """expired 트렌드 바이럴 점수 70%로 감소."""
    from core.pipeline import _ensure_quality_and_diversity

    trends = [
        _make_trend("최신뉴스", viral=90, category="테크", content_age_hours=0.5),
        _make_trend("어제뉴스", viral=90, category="연예", content_age_hours=30.0),
    ]

    result = _ensure_quality_and_diversity(trends, config)
    kw_map = {t.keyword: t for t in result}

    # 최신뉴스는 패널티 없음 (fresh: 0~6h)
    assert kw_map["최신뉴스"].viral_potential == 90
    # 어제뉴스는 expired(24h+) 0.7 배율 → 63점
    assert kw_map["어제뉴스"].viral_potential == int(90 * 0.7)


def test_stale_trend_penalty(config):
    """stale 트렌드 바이럴 점수 85%로 감소."""
    from core.pipeline import _ensure_quality_and_diversity

    trends = [
        _make_trend("반나절뉴스", viral=100, category="테크", content_age_hours=15.0),
    ]

    result = _ensure_quality_and_diversity(trends, config)
    assert result[0].viral_potential == int(100 * 0.85)  # stale: 12~24h


# ══════════════════════════════════════════════════════
#  [v6.1] RSS 날짜 파싱 테스트
# ══════════════════════════════════════════════════════


def test_parse_rss_date_valid():
    """유효한 RFC 2822 날짜 파싱."""
    from scraper import _parse_rss_date

    dt = _parse_rss_date("Thu, 05 Mar 2026 12:00:00 +0900")
    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 3
    assert dt.day == 5


def test_parse_rss_date_none():
    """None 입력 → None 반환."""
    from scraper import _parse_rss_date

    assert _parse_rss_date(None) is None
    assert _parse_rss_date("") is None


def test_parse_rss_date_invalid():
    """잘못된 형식 → None 반환."""
    from scraper import _parse_rss_date

    assert _parse_rss_date("not a date") is None


def test_format_news_age_recent():
    """최근 날짜 → '시간 전' 형식."""
    from scraper import _format_news_age
    from datetime import datetime as _dt, timezone as _tz

    # 2시간 전 날짜 만들기
    two_hours_ago = _dt.now(_tz.utc) - timedelta(hours=2)
    date_str = two_hours_ago.strftime("%a, %d %b %Y %H:%M:%S +0000")
    result = _format_news_age(date_str)
    assert "시간 전" in result


def test_format_news_age_none():
    """None → 빈 문자열."""
    from scraper import _format_news_age

    assert _format_news_age(None) == ""


# ══════════════════════════════════════════════════════
#  content_feedback DB 테스트
# ══════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_record_content_feedback(conn):
    """content_feedback 테이블에 QA 피드백이 정상 기록되는지 확인."""
    await record_content_feedback(
        conn,
        keyword="테스트키워드",
        category="테크",
        qa_score=72.5,
        regenerated=False,
        reason="톤 일관성 부족",
    )

    cursor = await conn.execute(
        "SELECT keyword, category, qa_score, regenerated, reason FROM content_feedback"
    )
    rows = await cursor.fetchall()
    assert len(rows) == 1
    row = dict(rows[0])
    assert row["keyword"] == "테스트키워드"
    assert row["category"] == "테크"
    assert row["qa_score"] == 72.5
    assert row["regenerated"] == 0
    assert row["reason"] == "톤 일관성 부족"


@pytest.mark.asyncio
async def test_record_content_feedback_with_freshness(conn):
    """v6.1: content_feedback에 freshness 메트릭이 정상 기록되는지 확인."""
    await record_content_feedback(
        conn,
        keyword="최신키워드",
        category="연예",
        qa_score=85.0,
        content_age_hours=2.5,
        freshness_grade="recent",
    )

    cursor = await conn.execute(
        "SELECT keyword, content_age_hours, freshness_grade FROM content_feedback WHERE keyword = '최신키워드'"
    )
    row = await cursor.fetchone()
    assert row is not None
    row_dict = dict(row)
    assert row_dict["content_age_hours"] == 2.5
    assert row_dict["freshness_grade"] == "recent"


@pytest.mark.asyncio
async def test_record_content_feedback_regenerated(conn):
    """재생성 케이스의 content_feedback 기록."""
    await record_content_feedback(
        conn,
        keyword="재생성키워드",
        category="연예",
        qa_score=35.0,
        regenerated=True,
        reason="사실 정확성 미달",
    )

    cursor = await conn.execute(
        "SELECT keyword, regenerated FROM content_feedback WHERE keyword = '재생성키워드'"
    )
    row = await cursor.fetchone()
    assert row is not None
    assert dict(row)["regenerated"] == 1


# ══════════════════════════════════════════════════════
#  Config 필드 테스트
# ══════════════════════════════════════════════════════


def test_v6_config_defaults():
    """v6.0 설정 기본값 확인."""
    cfg = AppConfig()
    assert cfg.min_article_count == 3  # [v13.0] 5→3으로 변경
    assert cfg.max_same_category == 2
    assert cfg.enable_quality_feedback is True
    assert cfg.quality_feedback_min_score == 50
    assert cfg.editorial_profile == "report"
    assert cfg.threads_quality_min_score == 65
    assert cfg.long_form_quality_min_score == 70
    assert cfg.blog_quality_min_score == 75


def test_v61_config_defaults():
    """v6.1 최신성 설정 기본값 확인."""
    cfg = AppConfig()
    assert cfg.max_content_age_hours == 24
    assert cfg.freshness_penalty_stale == 0.85
    assert cfg.freshness_penalty_expired == 0.7


def test_v6_config_from_env():
    """환경변수에서 v6.0 설정 로드."""
    with patch.dict(os.environ, {
        "MIN_ARTICLE_COUNT": "5",
        "MAX_SAME_CATEGORY": "3",
        "ENABLE_QUALITY_FEEDBACK": "false",
        "QUALITY_FEEDBACK_MIN_SCORE": "70",
        "EDITORIAL_PROFILE": "classic",
        "THREADS_QUALITY_MIN_SCORE": "68",
        "LONG_FORM_QUALITY_MIN_SCORE": "72",
        "BLOG_QUALITY_MIN_SCORE": "80",
    }):
        cfg = AppConfig.from_env()
        assert cfg.min_article_count == 5
        assert cfg.max_same_category == 3
        assert cfg.enable_quality_feedback is False
        assert cfg.quality_feedback_min_score == 70
        assert cfg.editorial_profile == "classic"
        assert cfg.threads_quality_min_score == 68
        assert cfg.long_form_quality_min_score == 72
        assert cfg.blog_quality_min_score == 80


def test_v61_config_from_env():
    """환경변수에서 v6.1 최신성 설정 로드."""
    with patch.dict(os.environ, {
        "MAX_CONTENT_AGE_HOURS": "6",
        "FRESHNESS_PENALTY_STALE": "0.9",
        "FRESHNESS_PENALTY_EXPIRED": "0.5",
    }):
        cfg = AppConfig.from_env()
        assert cfg.max_content_age_hours == 6
        assert cfg.freshness_penalty_stale == 0.9
        assert cfg.freshness_penalty_expired == 0.5
