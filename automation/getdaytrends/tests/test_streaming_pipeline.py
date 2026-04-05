"""
StreamingPipeline 통합 테스트 — v16.0 핵심 비동기 파이프라인 검증.

타겟: core/streaming_pipeline.py (StreamingPipeline, PipelineEvent)
커버리지:
  - Happy path: 전 단계(Score→Generate→Save) 정상 완료
  - Scorer/Generator/Saver 각 단계 타임아웃 및 예외 처리
  - Sentinel 동기화: generator 개수 != sentinel 수일 때 deadlock 방지 확인
  - Re-entrant safety: 동일 인스턴스 2회 실행 시 상태 오염 없음
  - Edge case: 빈 입력, 전체 실패, None generate_fn (dry-run)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

import importlib
import importlib.util
import sys

# core/__init__.py 가 shared.llm 을 전이 임포트해서 dotenv 에러 발생할 수 있으므로
# streaming_pipeline 모듈만 직접 로드한다.
# 먼저 core 패키지를 빈 모듈로 등록해서 __init__.py 의 전이 임포트를 우회.
if "core" not in sys.modules:
    import types as _types
    sys.modules["core"] = _types.ModuleType("core")

_spec = importlib.util.spec_from_file_location(
    "core.streaming_pipeline",
    str(__import__("pathlib").Path(__file__).resolve().parents[1] / "core" / "streaming_pipeline.py"),
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["core.streaming_pipeline"] = _mod
_spec.loader.exec_module(_mod)
PipelineEvent = _mod.PipelineEvent
StreamingPipeline = _mod.StreamingPipeline


# ── Helpers ──────────────────────────────────────────────────────────────────


@dataclass
class FakeTrend:
    name: str
    score: float = 0.0


@dataclass
class FakeBatch:
    topic: str
    tweet_count: int = 3


async def _score_fn(trend, context):
    """스코어링 stub — score 필드를 99로 설정."""
    trend.score = 99.0
    return trend


async def _generate_fn(scored_trend):
    """생성 stub — FakeBatch 반환."""
    return FakeBatch(topic=scored_trend.name)


async def _save_fn(trend, batch):
    """저장 stub — no-op."""
    pass


async def _slow_score_fn(trend, context):
    """타임아웃 유발용 스코어링."""
    await asyncio.sleep(999)
    return trend


async def _slow_generate_fn(scored_trend):
    """타임아웃 유발용 생성."""
    await asyncio.sleep(999)
    return FakeBatch(topic=scored_trend.name)


async def _slow_save_fn(trend, batch):
    """타임아웃 유발용 저장."""
    await asyncio.sleep(999)


async def _failing_score_fn(trend, context):
    raise ValueError(f"scoring exploded: {trend.name}")


async def _failing_generate_fn(scored_trend):
    raise RuntimeError(f"LLM unavailable: {scored_trend.name}")


async def _failing_save_fn(trend, batch):
    raise IOError("disk full")


# ── Fixtures ─────────────────────────────────────────────────────────────────


class _FakeConfig:
    dry_run = True


class _FakeConn:
    pass


@pytest.fixture
def pipeline():
    """기본 파이프라인 인스턴스 (gen_concurrency=2)."""
    sp = StreamingPipeline(_FakeConfig(), _FakeConn(), generator_concurrency=2)
    sp.STAGE_TIMEOUT_SECONDS = 1  # 테스트에서 빠르게 타임아웃 감지
    return sp


@pytest.fixture
def trends():
    return [FakeTrend(name=f"trend-{i}") for i in range(5)]


@pytest.fixture
def contexts(trends):
    return {t.name: {"source": "test"} for t in trends}


# ══════════════════════════════════════════════════════════════════════════════
#  Happy Path
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_happy_path_all_stages_complete(pipeline, trends, contexts):
    """정상 흐름: 5개 트렌드 → 모두 scored → generated → saved."""
    results = await pipeline.run(
        trends, contexts,
        score_fn=_score_fn, generate_fn=_generate_fn, save_fn=_save_fn,
    )

    assert len(results) == 5
    for event in results:
        assert event.error == ""
        assert event.stage == "saved"
        assert isinstance(event.result, FakeBatch)
        assert event.completed_at is not None
        assert event.elapsed_ms > 0

    assert pipeline.success_count == 5
    assert pipeline.error_count == 0


@pytest.mark.asyncio
async def test_happy_path_no_generate_fn_dryrun(pipeline, trends, contexts):
    """generate_fn=None → dry-run 모드, batch는 None이지만 에러 없음."""
    results = await pipeline.run(
        trends, contexts,
        score_fn=_score_fn, generate_fn=None, save_fn=_save_fn,
    )

    assert len(results) == 5
    for event in results:
        assert event.error == ""
        # save_fn은 호출되지만 event.result가 None이므로 save_fn 내부에서 skip
        assert event.result is None


@pytest.mark.asyncio
async def test_happy_path_no_score_fn_passthrough(pipeline, trends, contexts):
    """score_fn=None → 트렌드가 그대로 통과."""
    results = await pipeline.run(
        trends, contexts,
        score_fn=None, generate_fn=_generate_fn, save_fn=_save_fn,
    )

    assert len(results) == 5
    for event in results:
        assert event.error == ""
        assert isinstance(event.result, FakeBatch)


# ══════════════════════════════════════════════════════════════════════════════
#  Timeout & Exception — Scorer
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_scorer_timeout_does_not_deadlock(pipeline, trends, contexts):
    """스코어링 타임아웃 → 해당 트렌드만 에러, 파이프라인 정상 종료 (deadlock 없음)."""
    results = await asyncio.wait_for(
        pipeline.run(
            trends, contexts,
            score_fn=_slow_score_fn, generate_fn=_generate_fn, save_fn=_save_fn,
        ),
        timeout=30,  # 전체 파이프라인이 30초 내에 끝나야 함 (deadlock 감지)
    )

    # 모든 트렌드가 타임아웃 → results는 빈 리스트 (scored_queue에 안 들어감)
    assert len(results) == 0
    assert pipeline.error_count == 5


@pytest.mark.asyncio
async def test_scorer_exception_propagates_as_error(pipeline, contexts):
    """스코어링 예외 → 에러 문자열에 원인 포함, 나머지 트렌드 계속 처리."""
    trends = [FakeTrend(name="good"), FakeTrend(name="bad")]

    call_count = 0

    async def mixed_score_fn(trend, ctx):
        nonlocal call_count
        call_count += 1
        if trend.name == "bad":
            raise ValueError("bad trend!")
        trend.score = 50.0
        return trend

    results = await pipeline.run(
        trends, {t.name: {} for t in trends},
        score_fn=mixed_score_fn, generate_fn=_generate_fn, save_fn=_save_fn,
    )

    # "good" 트렌드는 정상 저장, "bad"는 스코어링에서 탈락 (results에 안 들어감)
    saved = [r for r in results if not r.error]
    assert len(saved) == 1
    assert saved[0].result.topic == "good"

    # 에러 1건 기록
    assert pipeline.error_count >= 1


# ══════════════════════════════════════════════════════════════════════════════
#  Timeout & Exception — Generator
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_generator_timeout_captured_in_event(pipeline, trends, contexts):
    """생성 타임아웃 → event.error에 기록, 파이프라인 정상 종료."""
    results = await asyncio.wait_for(
        pipeline.run(
            trends, contexts,
            score_fn=_score_fn, generate_fn=_slow_generate_fn, save_fn=_save_fn,
        ),
        timeout=30,
    )

    assert len(results) == 5
    for event in results:
        assert "generation_timeout" in event.error
    assert pipeline.success_count == 0
    assert pipeline.error_count == 5


@pytest.mark.asyncio
async def test_generator_exception_captured_in_event(pipeline, trends, contexts):
    """생성 예외 → event.error에 기록, saver가 해당 이벤트를 skip."""
    results = await pipeline.run(
        trends, contexts,
        score_fn=_score_fn, generate_fn=_failing_generate_fn, save_fn=_save_fn,
    )

    assert len(results) == 5
    for event in results:
        assert "generation_error" in event.error
        assert "LLM unavailable" in event.error


# ══════════════════════════════════════════════════════════════════════════════
#  Timeout & Exception — Saver
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_saver_timeout_captured_in_event(pipeline, trends, contexts):
    """저장 타임아웃 → event.error에 기록."""
    results = await asyncio.wait_for(
        pipeline.run(
            trends, contexts,
            score_fn=_score_fn, generate_fn=_generate_fn, save_fn=_slow_save_fn,
        ),
        timeout=30,
    )

    assert len(results) == 5
    for event in results:
        assert "save_timeout" in event.error


@pytest.mark.asyncio
async def test_saver_exception_captured_in_event(pipeline, trends, contexts):
    """저장 예외 → event.error에 기록, 나머지 트렌드 계속."""
    results = await pipeline.run(
        trends, contexts,
        score_fn=_score_fn, generate_fn=_generate_fn, save_fn=_failing_save_fn,
    )

    assert len(results) == 5
    for event in results:
        assert "save_error" in event.error
        assert "disk full" in event.error


# ══════════════════════════════════════════════════════════════════════════════
#  Re-entrant Safety (v16.0 QA fix regression)
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_reentrant_run_does_not_leak_state(pipeline, contexts):
    """동일 인스턴스 2회 실행 시 첫 번째 결과가 두 번째에 오염되지 않음."""
    trends_1 = [FakeTrend(name="run1-a"), FakeTrend(name="run1-b")]
    trends_2 = [FakeTrend(name="run2-x")]

    results_1 = await pipeline.run(
        trends_1, {t.name: {} for t in trends_1},
        score_fn=_score_fn, generate_fn=_generate_fn, save_fn=_save_fn,
    )
    results_2 = await pipeline.run(
        trends_2, {t.name: {} for t in trends_2},
        score_fn=_score_fn, generate_fn=_generate_fn, save_fn=_save_fn,
    )

    assert len(results_1) == 2
    assert len(results_2) == 1
    # 두 번째 실행의 결과에 첫 번째 실행 데이터가 없어야 함
    assert all(r.result.topic.startswith("run2") for r in results_2)
    assert pipeline.success_count == 1  # 마지막 실행 기준
    assert pipeline.error_count == 0


# ══════════════════════════════════════════════════════════════════════════════
#  Edge Cases
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_empty_input_returns_empty_results(pipeline):
    """빈 트렌드 리스트 → 빈 결과, deadlock 없음."""
    results = await asyncio.wait_for(
        pipeline.run([], {}, score_fn=_score_fn, generate_fn=_generate_fn, save_fn=_save_fn),
        timeout=10,
    )

    assert results == []
    assert pipeline.success_count == 0
    assert pipeline.error_count == 0


@pytest.mark.asyncio
async def test_single_trend_single_concurrency():
    """generator_concurrency=1 → sentinel 1개로 정상 종료."""
    sp = StreamingPipeline(_FakeConfig(), _FakeConn(), generator_concurrency=1)
    sp.STAGE_TIMEOUT_SECONDS = 5

    trend = FakeTrend(name="solo")
    results = await sp.run(
        [trend], {"solo": {}},
        score_fn=_score_fn, generate_fn=_generate_fn, save_fn=_save_fn,
    )

    assert len(results) == 1
    assert results[0].error == ""
    assert results[0].result.topic == "solo"


@pytest.mark.asyncio
async def test_high_concurrency_more_workers_than_trends():
    """generator_concurrency(5) > trends(2) → 잉여 worker가 즉시 종료."""
    sp = StreamingPipeline(_FakeConfig(), _FakeConn(), generator_concurrency=5)
    sp.STAGE_TIMEOUT_SECONDS = 5

    trends = [FakeTrend(name="a"), FakeTrend(name="b")]
    results = await asyncio.wait_for(
        sp.run(
            trends, {t.name: {} for t in trends},
            score_fn=_score_fn, generate_fn=_generate_fn, save_fn=_save_fn,
        ),
        timeout=10,
    )

    assert len(results) == 2
    assert sp.success_count == 2


@pytest.mark.asyncio
async def test_all_scores_fail_generators_still_exit():
    """전체 스코어링 실패 → generator들이 sentinel 받고 정상 종료 (deadlock 방지 핵심)."""
    sp = StreamingPipeline(_FakeConfig(), _FakeConn(), generator_concurrency=3)
    sp.STAGE_TIMEOUT_SECONDS = 1

    trends = [FakeTrend(name=f"fail-{i}") for i in range(4)]

    results = await asyncio.wait_for(
        sp.run(
            trends, {t.name: {} for t in trends},
            score_fn=_failing_score_fn, generate_fn=_generate_fn, save_fn=_save_fn,
        ),
        timeout=15,
    )

    # 스코어링 실패한 트렌드는 scored_queue에 안 들어가므로 results는 비어있음
    assert len(results) == 0
    assert sp.error_count == 4


# ══════════════════════════════════════════════════════════════════════════════
#  PipelineEvent unit tests
# ══════════════════════════════════════════════════════════════════════════════


def test_pipeline_event_complete_sets_fields():
    event = PipelineEvent(trend="test")
    assert event.elapsed_ms == 0.0  # 완료 전

    event.complete(result="batch_data", error="")
    assert event.result == "batch_data"
    assert event.error == ""
    assert event.completed_at is not None
    assert event.elapsed_ms > 0


def test_pipeline_event_complete_with_error():
    event = PipelineEvent(trend="test")
    event.complete(error="timeout")
    assert event.error == "timeout"
    assert event.result is None


# ══════════════════════════════════════════════════════════════════════════════
#  TAP _is_same_topic — false positive 방지
# ══════════════════════════════════════════════════════════════════════════════


class TestIsSameTopic:
    """tap/detector.py의 _is_same_topic 토픽 유사도 판별 검증."""

    @pytest.fixture(autouse=True)
    def _import(self):
        # tap/__init__.py 가 service 를 전이 임포트하여 에러 발생할 수 있으므로 직접 로드
        # _tap_detector 라는 별도 이름으로 로드하여 sys.modules["tap"] 오염 방지
        if "_tap_detector" not in sys.modules:
            _s = importlib.util.spec_from_file_location(
                "_tap_detector",
                str(__import__("pathlib").Path(__file__).resolve().parents[1] / "tap" / "detector.py"),
            )
            _m = importlib.util.module_from_spec(_s)
            sys.modules["_tap_detector"] = _m
            _s.loader.exec_module(_m)
        _det = sys.modules["_tap_detector"]
        self.is_same_topic = _det._is_same_topic
        self.normalize = _det._normalize_keyword

    # ── 정확 매치 ──

    def test_exact_match(self):
        assert self.is_same_topic("AI", "AI") is True

    def test_case_insensitive_match(self):
        assert self.is_same_topic("ChatGPT", "chatgpt") is True

    def test_whitespace_and_dash_ignored(self):
        assert self.is_same_topic("AI Agent", "ai-agent") is True

    # ── 부분 문자열 포함 ──

    def test_substring_containment(self):
        assert self.is_same_topic("AI", "AI Agent") is True

    def test_substring_containment_reverse(self):
        assert self.is_same_topic("OpenAI GPT", "GPT") is True

    # ── Jaccard bigram 유사도 ──

    def test_similar_long_keywords_above_threshold(self):
        # "machinelearning" vs "machinelearn" → 높은 bigram 겹침
        assert self.is_same_topic("Machine Learning", "Machine Learn") is True

    def test_different_keywords_below_threshold(self):
        assert self.is_same_topic("blockchain", "basketball") is False

    # ── Edge Cases (false positive 방지) ──

    def test_empty_strings_return_false(self):
        assert self.is_same_topic("", "") is False
        assert self.is_same_topic("AI", "") is False
        assert self.is_same_topic("", "AI") is False

    def test_single_char_no_bigram_no_false_match(self):
        """단일 문자 키워드 → bigram 불가, 정확/부분 매치만 적용."""
        assert self.is_same_topic("A", "B") is False

    def test_short_distinct_keywords_no_false_positive(self):
        """짧은 키워드 간 false positive 방지: 'AB' vs 'CD'."""
        assert self.is_same_topic("AB", "CD") is False

    def test_korean_keywords_exact(self):
        assert self.is_same_topic("인공지능", "인공지능") is True

    def test_korean_keywords_different(self):
        assert self.is_same_topic("인공지능", "블록체인") is False

    def test_korean_substring(self):
        assert self.is_same_topic("인공", "인공지능") is True

    def test_threshold_boundary(self):
        """threshold=1.0 → 정확 bigram 매치만 허용."""
        assert self.is_same_topic("abcdef", "abcdeg", threshold=1.0) is False

    # ── Normalize ──

    def test_normalize_strips_special_chars(self):
        assert self.normalize("AI-Agent_Test ") == "aiagenttest"
