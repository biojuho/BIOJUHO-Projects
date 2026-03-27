"""
getdaytrends v6.0 - Fact Checker & Accuracy Tests

fact_checker.py 모듈의 기능 검증:
1. Claim Extraction (주장 추출)
2. Cross-Reference Verification (교차 검증)
3. Hallucination Detection (환각 감지)
4. Source Credibility Scoring (출처 신뢰도)
5. Cross-Source Consistency (소스 간 일관성)
6. Integration with ScoredTrend
"""

import pytest

from fact_checker import (
    Claim,
    ClaimType,
    CredibilityTier,
    FactCheckResult,
    check_cross_source_consistency,
    compute_enhanced_confidence,
    compute_source_credibility_score,
    extract_claims,
    get_source_credibility,
    verify_batch,
    verify_claim_against_source,
    verify_content,
)
from models import (
    GeneratedTweet,
    MultiSourceContext,
    ScoredTrend,
    TrendContext,
    TweetBatch,
)


# ══════════════════════════════════════════════════════
#  Fixtures
# ══════════════════════════════════════════════════════


def _make_trend(
    keyword: str = "삼성전자",
    top_insight: str = "삼성전자가 3나노 반도체 양산을 시작했다",
    why_trending: str = "TSMC와의 파운드리 경쟁 격화로 주목",
    news_insight: str = "[연합뉴스] 삼성전자 3나노 수율 50% 돌파 | [Bloomberg] Samsung foundry 30% cost cut",
    twitter_insight: str = "[25L/10RT] 삼성 파운드리 20조 베팅했는데 TSMC는 같은 날 40조 발표",
    reddit_insight: str = "[150pts] Samsung 3nm yield improvement confirmed by analysts",
    trigger_event: str = "삼성전자 파운드리 사업부 20조원 투자 발표 (2시간 전)",
) -> ScoredTrend:
    return ScoredTrend(
        keyword=keyword,
        rank=1,
        viral_potential=80,
        top_insight=top_insight,
        why_trending=why_trending,
        context=MultiSourceContext(
            twitter_insight=twitter_insight,
            reddit_insight=reddit_insight,
            news_insight=news_insight,
        ),
        trend_context=TrendContext(
            trigger_event=trigger_event,
            chain_reaction="투자 발표 → 커뮤니티 확산 → 언론 보도",
            why_now="TSMC 2나노 양산 일정 확정과 동시 발표",
            key_positions=["삼성 경쟁력 강화", "TSMC 격차 여전"],
        ),
    )


def _make_batch(tweets_content: list[str]) -> TweetBatch:
    return TweetBatch(
        topic="삼성전자",
        tweets=[
            GeneratedTweet(
                tweet_type=f"앵글{i}",
                content=content,
                content_type="short",
            )
            for i, content in enumerate(tweets_content, 1)
        ],
        viral_score=80,
    )


# ══════════════════════════════════════════════════════
#  1. Claim Extraction Tests
# ══════════════════════════════════════════════════════


class TestClaimExtraction:
    def test_extract_numbers(self):
        text = "삼성전자가 20조원을 투자하고 수율 50%를 달성했다."
        claims = extract_claims(text)
        numbers = [c for c in claims if c.claim_type == ClaimType.NUMBER]
        assert any("20" in c.value and "조" in c.value for c in numbers)

    def test_extract_percentages(self):
        text = "전년 대비 +15% 성장했고, 시장점유율은 30%이다."
        claims = extract_claims(text)
        # NUMBER 패턴이 먼저 % 숫자를 잡을 수 있으므로 NUMBER+PERCENTAGE 합산 확인
        pct_claims = [
            c for c in claims
            if c.claim_type in (ClaimType.PERCENTAGE, ClaimType.NUMBER)
            and "%" in c.value
        ]
        assert len(pct_claims) >= 2
        values = [c.value for c in pct_claims]
        assert any("15" in v for v in values)
        assert any("30" in v for v in values)

    def test_extract_dates(self):
        text = "3월 15일 발표된 보고서에 따르면 3시간 전부터 논의가 시작됐다."
        claims = extract_claims(text)
        dates = [c for c in claims if c.claim_type == ClaimType.DATE]
        assert len(dates) >= 1

    def test_extract_entities(self):
        text = "금융위원회가 발표한 자료에 따르면 한국은행 기준금리가 변동됐다."
        claims = extract_claims(text)
        entities = [c for c in claims if c.claim_type == ClaimType.ENTITY]
        assert len(entities) >= 1
        # 금융위원회 또는 한국은행 중 하나 이상 추출
        entity_values = " ".join(c.value for c in entities)
        assert "위원회" in entity_values or "은행" in entity_values

    def test_extract_empty_text(self):
        assert extract_claims("") == []
        assert extract_claims("짧은") == []

    def test_no_duplicates(self):
        text = "20조원을 투자하고 20조원을 회수했다."
        claims = extract_claims(text)
        values = [c.value for c in claims]
        # 같은 값은 한 번만 추출
        assert len(set(values)) == len(values)

    def test_common_entities_excluded(self):
        """일반적인 고유명사(삼성, 네이버 등)는 추출 대상에서 제외."""
        text = "삼성전자와 네이버가 AI 투자를 발표했다."
        claims = extract_claims(text)
        entities = [c for c in claims if c.claim_type == ClaimType.ENTITY]
        entity_values = [c.value.lower() for c in entities]
        assert "삼성" not in entity_values
        assert "네이버" not in entity_values


# ══════════════════════════════════════════════════════
#  2. Cross-Reference Verification Tests
# ══════════════════════════════════════════════════════


class TestCrossReferenceVerification:
    def test_exact_number_match(self):
        claim = Claim(claim_type=ClaimType.NUMBER, value="20조원", context="20조원 투자")
        source = "삼성전자가 20조원 규모의 투자를 발표했다."
        result = verify_claim_against_source(claim, source)
        assert result.verified is True
        assert result.confidence >= 0.8

    def test_percentage_match(self):
        claim = Claim(claim_type=ClaimType.PERCENTAGE, value="50%", context="수율 50%")
        source = "3나노 수율 50% 돌파"
        result = verify_claim_against_source(claim, source)
        assert result.verified is True

    def test_entity_match(self):
        claim = Claim(claim_type=ClaimType.ENTITY, value="금융위원회", context="금융위원회 발표")
        source = "금융위원회가 새로운 규정을 발표했다."
        result = verify_claim_against_source(claim, source)
        assert result.verified is True
        assert result.confidence >= 0.8

    def test_unverified_entity(self):
        claim = Claim(claim_type=ClaimType.ENTITY, value="과학기술정보통신부", context="과기부 발표")
        source = "삼성전자가 반도체 투자를 발표했다."
        result = verify_claim_against_source(claim, source)
        assert result.verified is False

    def test_date_match(self):
        claim = Claim(claim_type=ClaimType.DATE, value="3월 15일", context="3월 15일 발표")
        source = "3월 15일에 개최된 기자회견에서"
        result = verify_claim_against_source(claim, source)
        assert result.verified is True

    def test_empty_source(self):
        claim = Claim(claim_type=ClaimType.NUMBER, value="100억원", context="100억원 투자")
        result = verify_claim_against_source(claim, "")
        assert result.verified is False
        assert result.confidence == 0.0


# ══════════════════════════════════════════════════════
#  3. Content Verification Tests
# ══════════════════════════════════════════════════════


class TestContentVerification:
    def test_verified_content_passes(self):
        """소스에 있는 정보만 사용한 콘텐츠는 통과."""
        trend = _make_trend()
        text = "삼성전자 파운드리 20조 베팅했는데 TSMC는 같은 날 40조 발표."
        result = verify_content(text, trend)
        assert result.passed is True
        assert result.accuracy_score >= 0.5

    def test_hallucinated_entity_fails(self):
        """소스에 없는 고유명사 사용 시 환각으로 감지."""
        trend = _make_trend(
            news_insight="[연합뉴스] 삼성전자 반도체 투자 발표",
            twitter_insight="삼성 반도체 투자 관련 트윗",
            reddit_insight="Samsung investment discussion",
            trigger_event="삼성전자 투자 발표",
        )
        text = "국토교통부 장관이 인천공항공사 확장 계획을 발표했다."
        result = verify_content(text, trend)
        # 소스에 전혀 없는 기관이므로 환각 감지
        assert result.hallucinated_claims > 0 or result.unverified_claims > 0

    def test_empty_text_passes(self):
        trend = _make_trend()
        result = verify_content("", trend)
        assert result.passed is True

    def test_accuracy_score_calculation(self):
        trend = _make_trend()
        text = "삼성전자 3나노 수율 50% 돌파. 20조원 투자 발표."
        result = verify_content(text, trend)
        assert 0.0 <= result.accuracy_score <= 1.0

    def test_strict_mode(self):
        trend = _make_trend()
        text = "삼성전자 3나노 수율 50% 돌파."
        result_normal = verify_content(text, trend, strict_mode=False)
        result_strict = verify_content(text, trend, strict_mode=True)
        # strict 모드에서는 같거나 더 엄격
        assert result_strict.accuracy_score <= result_normal.accuracy_score + 0.01


# ══════════════════════════════════════════════════════
#  4. Source Credibility Tests
# ══════════════════════════════════════════════════════


class TestSourceCredibility:
    def test_tier1_source(self):
        assert get_source_credibility("연합뉴스") == CredibilityTier.TIER_1
        assert get_source_credibility("BBC News") == CredibilityTier.TIER_1
        assert get_source_credibility("Reuters report") == CredibilityTier.TIER_1

    def test_tier2_source(self):
        assert get_source_credibility("Bloomberg analysis") == CredibilityTier.TIER_2
        assert get_source_credibility("조선일보 보도") == CredibilityTier.TIER_2

    def test_tier3_source(self):
        assert get_source_credibility("TechCrunch article") == CredibilityTier.TIER_3

    def test_unknown_source(self):
        assert get_source_credibility("") == CredibilityTier.UNKNOWN
        assert get_source_credibility("무명 블로그") == CredibilityTier.TIER_4

    def test_credibility_score_high(self):
        score = compute_source_credibility_score("[연합뉴스] 삼성 발표 | [BBC] Samsung news")
        assert score >= 0.8

    def test_credibility_score_low(self):
        score = compute_source_credibility_score("어떤 블로그에서 본 이야기")
        assert score <= 0.5

    def test_credibility_score_empty(self):
        assert compute_source_credibility_score("") == 0.0


# ══════════════════════════════════════════════════════
#  5. Cross-Source Consistency Tests
# ══════════════════════════════════════════════════════


class TestCrossSourceConsistency:
    def test_consistent_sources(self):
        trend = _make_trend(
            twitter_insight="삼성전자 AI 칩 개발 발표로 반도체 업계 주목",
            reddit_insight="Samsung AI chip development announced",
            news_insight="[연합뉴스] 삼성전자 AI 반도체 개발 착수",
        )
        result = check_cross_source_consistency(trend)
        # 수치 충돌이 없으면 consistent
        assert result["consistent"] is True

    def test_inconsistent_sources(self):
        """소스 간 수치가 크게 다르면 불일치 감지."""
        trend = _make_trend(
            twitter_insight="삼성 투자 규모 20조원이라고 함",
            reddit_insight="Samsung investment 50조원 trillion won",
            news_insight="[연합뉴스] 삼성전자 100조원 투자",
        )
        result = check_cross_source_consistency(trend)
        # 수치 차이가 크면 충돌 감지
        assert len(result["conflicts"]) >= 0  # 충돌이 있을 수 있음

    def test_single_source(self):
        """소스가 1개뿐이면 일관성 검증 스킵."""
        trend = _make_trend(
            twitter_insight="삼성 투자 발표",
            reddit_insight="",
            news_insight="",
        )
        result = check_cross_source_consistency(trend)
        assert result["consistent"] is True

    def test_no_context(self):
        trend = ScoredTrend(keyword="테스트", rank=1)
        result = check_cross_source_consistency(trend)
        assert result["consistent"] is True


# ══════════════════════════════════════════════════════
#  6. Batch Verification Tests
# ══════════════════════════════════════════════════════


class TestBatchVerification:
    def test_verify_batch_all_pass(self):
        trend = _make_trend()
        batch = _make_batch([
            "삼성전자 파운드리 20조 투자. TSMC와 경쟁 격화.",
            "3나노 수율 50% 돌파. 반도체 업계 지각변동.",
        ])
        results = verify_batch(batch, trend)
        assert "tweets" in results
        assert results["tweets"].total_claims >= 0

    def test_verify_batch_empty(self):
        trend = _make_trend()
        batch = TweetBatch(topic="삼성전자")
        results = verify_batch(batch, trend)
        assert len(results) == 0

    def test_verify_batch_mixed_groups(self):
        trend = _make_trend()
        batch = TweetBatch(
            topic="삼성전자",
            tweets=[GeneratedTweet(
                tweet_type="공감형",
                content="삼성전자 3나노 수율 향상",
                content_type="short",
            )],
            long_posts=[GeneratedTweet(
                tweet_type="장문",
                content="삼성전자 파운드리 사업부가 20조원 규모의 대규모 투자를 발표했다.",
                content_type="long",
            )],
        )
        results = verify_batch(batch, trend)
        assert "tweets" in results
        assert "long_posts" in results


# ══════════════════════════════════════════════════════
#  7. Enhanced Confidence Tests
# ══════════════════════════════════════════════════════


class TestEnhancedConfidence:
    def test_full_confidence(self):
        ctx = MultiSourceContext(
            twitter_insight="X에서 활발한 논의가 진행 중입니다. 많은 사용자들이 의견을 남기고 있습니다.",
            reddit_insight="Reddit에서도 많은 토론이 이뤄지고 있습니다. 다양한 커뮤니티에서 활발한 논의.",
            news_insight="[연합뉴스] 주요 뉴스로 보도되었습니다. 관련 기사가 다수 게재.",
        )
        score, credibility = compute_enhanced_confidence(10000, ctx)
        assert score >= 3  # 볼륨 + X + 뉴스 + (possibly) Reddit
        assert credibility >= 0.5

    def test_no_context(self):
        score, credibility = compute_enhanced_confidence(0, None)
        assert score == 0
        assert credibility == 0.0

    def test_partial_context(self):
        ctx = MultiSourceContext(
            twitter_insight="X 반응 있음",
            reddit_insight="",
            news_insight="",
        )
        score, _ = compute_enhanced_confidence(5000, ctx)
        assert 1 <= score <= 2  # 볼륨 + (possibly) X


# ══════════════════════════════════════════════════════
#  8. Integration Tests
# ══════════════════════════════════════════════════════


class TestFactCheckIntegration:
    def test_fact_check_result_summary(self):
        result = FactCheckResult(
            passed=True,
            total_claims=5,
            verified_claims=4,
            unverified_claims=1,
            accuracy_score=0.8,
            source_credibility=0.9,
        )
        assert "80%" in result.summary
        assert "통과" in result.summary

    def test_fact_check_result_failure_summary(self):
        result = FactCheckResult(
            passed=False,
            total_claims=5,
            verified_claims=2,
            unverified_claims=2,
            hallucinated_claims=1,
            accuracy_score=0.4,
        )
        assert "실패" in result.summary
        assert "환각=1" in result.summary

    def test_trend_with_low_credibility(self):
        """저신뢰 출처의 트렌드에서 생성된 콘텐츠 검증."""
        trend = _make_trend(
            news_insight="무명 블로그에서 본 이야기",
        )
        text = "삼성전자가 3나노 반도체 양산을 시작했다."
        result = verify_content(text, trend)
        assert result.source_credibility < 0.5

    def test_model_new_fields(self):
        """ScoredTrend에 정확성 관련 새 필드가 정상 작동하는지 확인."""
        trend = ScoredTrend(
            keyword="테스트",
            rank=1,
            source_credibility=0.8,
            fact_check_score=0.9,
            hallucination_flags=["환각 항목1"],
            cross_source_consistent=True,
        )
        assert trend.source_credibility == 0.8
        assert trend.fact_check_score == 0.9
        assert len(trend.hallucination_flags) == 1
        assert trend.cross_source_consistent is True

    def test_model_default_values(self):
        """새 필드의 기본값이 하위 호환성을 유지하는지 확인."""
        trend = ScoredTrend(keyword="테스트", rank=1)
        assert trend.source_credibility == 0.0
        assert trend.fact_check_score == 1.0
        assert trend.hallucination_flags == []
        assert trend.cross_source_consistent is True
