"""structured_output.py 테스트 — Instructor 구조화된 출력 모듈."""

import pytest

from structured_output import (
    ScoringResponseItem,
    TweetGenerationResponse,
    TweetItem,
    LongPostResponse,
    ThreadResponse,
    reset_instructor_client,
)


class TestScoringResponseItem:
    """ScoringResponseItem Pydantic 모델 테스트."""

    def test_default_values(self):
        item = ScoringResponseItem(keyword="테스트")
        assert item.keyword == "테스트"
        assert item.publishable is True
        assert item.viral_potential == 0
        assert item.sentiment == "neutral"
        assert item.safety_flag is False

    def test_full_construction(self):
        item = ScoringResponseItem(
            keyword="삼성전자",
            publishable=True,
            viral_potential=85,
            top_insight="반도체 투자 확대",
            why_trending="TSMC 대비 경쟁력 분석",
            peak_status="상승중",
            relevance_score=8,
            suggested_angles=["반전", "데이터", "공감"],
            best_hook_starter="3일 만에 2000억 증발",
            category="경제",
            sentiment="neutral",
            trigger_event="실적 발표",
            chain_reaction="커뮤니티 확산",
            why_now="실적 시즌",
            key_positions=["긍정론", "부정론"],
            joongyeon_kick=75,
        )
        assert item.viral_potential == 85
        assert item.category == "경제"
        assert len(item.suggested_angles) == 3

    def test_model_dump_compatibility(self):
        """model_dump()가 기존 _parse_json dict와 동일한 키 구조."""
        item = ScoringResponseItem(keyword="테스트", viral_potential=50)
        d = item.model_dump()
        assert "keyword" in d
        assert "viral_potential" in d
        assert "publishable" in d
        assert d["viral_potential"] == 50


class TestTweetGenerationResponse:
    """TweetGenerationResponse 모델 테스트."""

    def test_empty(self):
        resp = TweetGenerationResponse()
        assert resp.topic == ""
        assert resp.tweets == []

    def test_with_tweets(self):
        resp = TweetGenerationResponse(
            topic="삼성전자",
            tweets=[
                TweetItem(type="반전", content="근데 진짜 포인트는 돈이 아님"),
                TweetItem(type="데이터", content="3나노 수율 50% 못 넘기고 있는 동안"),
            ],
        )
        assert len(resp.tweets) == 2
        assert resp.tweets[0].content.startswith("근데")

    def test_model_dump_for_generator(self):
        """model_dump()가 generator.py의 data.get("tweets", []) 호환."""
        resp = TweetGenerationResponse(
            topic="테스트",
            tweets=[TweetItem(type="반전", content="테스트 내용")],
        )
        d = resp.model_dump()
        assert "tweets" in d
        assert d["tweets"][0]["content"] == "테스트 내용"
        assert d["tweets"][0]["type"] == "반전"


class TestLongPostResponse:
    """LongPostResponse 모델 테스트."""

    def test_with_seo(self):
        resp = LongPostResponse(
            topic="AI",
            content="장문 콘텐츠...",
            seo_keywords=["인공지능", "GPT"],
        )
        assert len(resp.seo_keywords) == 2


class TestThreadResponse:
    """ThreadResponse 모델 테스트."""

    def test_thread_structure(self):
        resp = ThreadResponse(
            topic="트렌드",
            hook="이거 왜 아무도 모르는 거임?",
            tweets=["첫 번째", "두 번째", "세 번째"],
        )
        assert len(resp.tweets) == 3
        assert resp.hook.endswith("?")


class TestResetClient:
    """클라이언트 리셋 테스트."""

    def test_reset_does_not_error(self):
        reset_instructor_client()  # 초기 상태에서도 에러 없이 동작해야 함
