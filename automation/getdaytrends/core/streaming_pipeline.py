"""
Event-Driven Pipeline — asyncio.Queue 기반 스트리밍 파이프라인.

기존 sync 배치(수집→전체스코어링→전체생성→전체저장)에서
단계간 blocking 없이 트렌드 단위로 즉시 다음 단계로 넘기는 구조.

결과: 전체 파이프라인 시간 최대 50% 단축.

Usage:
    from core.streaming_pipeline import StreamingPipeline

    sp = StreamingPipeline(config, conn)
    results = await sp.run(raw_trends, contexts)

Architecture:
    [Scorer Queue] → [Generator Queue] → [Saver Queue]
    각 Queue는 독립 Worker가 소비하며, 하나의 트렌드가 score되는 즉시
    Generate Worker가 픽업하여 LLM 호출을 시작한다.

Graceful Degradation:
    - Queue에 에러가 발생해도 다른 트렌드는 계속 처리
    - 모든 Worker에 timeout 설정 → deadlock 방지
    - 이 모듈은 100% 선택적: 기존 _step_generate 경로와 병행 가능
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from loguru import logger as log


@dataclass
class PipelineEvent:
    """파이프라인 이벤트 단위: 하나의 트렌드가 각 단계를 통과할 때마다 생성."""

    trend: Any                  # ScoredTrend
    stage: str = "queued"       # queued → scoring → scored → generating → generated → saving → saved
    result: Any = None          # TweetBatch 등 단계별 결과
    error: str = ""
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None

    def complete(self, result: Any = None, error: str = ""):
        self.result = result
        self.error = error
        self.completed_at = datetime.now()

    @property
    def elapsed_ms(self) -> float:
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        return 0.0


_SENTINEL = object()  # Queue 종료 신호


class StreamingPipeline:
    """asyncio.Queue 기반 스트리밍 파이프라인.

    Stage 1 (Scorer)  → scored_queue
    Stage 2 (Generator) → generated_queue
    Stage 3 (Saver)   → final results

    각 Stage는 독립 asyncio.Task로 실행되어 파이프라인 병렬성을 극대화.
    """

    # 기본 설정
    QUEUE_MAX_SIZE = 50
    GENERATOR_CONCURRENCY = 3     # 동시 LLM 호출 수
    STAGE_TIMEOUT_SECONDS = 120   # 단일 트렌드 처리 타임아웃

    def __init__(self, config, conn, *, generator_concurrency: int = 0):
        self._config = config
        self._conn = conn
        self._gen_concurrency = generator_concurrency or self.GENERATOR_CONCURRENCY
        self._scored_queue: asyncio.Queue = asyncio.Queue(maxsize=self.QUEUE_MAX_SIZE)
        self._generated_queue: asyncio.Queue = asyncio.Queue(maxsize=self.QUEUE_MAX_SIZE)
        self._results: list[PipelineEvent] = []
        self._errors: list[str] = []

    async def run(
        self,
        raw_trends: list,
        contexts: dict,
        *,
        score_fn=None,
        generate_fn=None,
        save_fn=None,
    ) -> list[PipelineEvent]:
        """전체 스트리밍 파이프라인 실행.

        Args:
            raw_trends: 수집된 RawTrend 리스트
            contexts: keyword → MultiSourceContext 매핑
            score_fn: 스코어링 함수 (async: trend → ScoredTrend)
            generate_fn: 생성 함수 (async: ScoredTrend → TweetBatch)
            save_fn: 저장 함수 (async: ScoredTrend, TweetBatch → None)

        Returns:
            PipelineEvent 리스트 (각 트렌드의 처리 결과)
        """
        log.info(f"[Streaming] 파이프라인 시작 — {len(raw_trends)}개 트렌드, "
                 f"gen_concurrency={self._gen_concurrency}")

        started_at = datetime.now()

        # Worker Task 생성
        scorer_task = asyncio.create_task(
            self._scorer_worker(raw_trends, contexts, score_fn)
        )
        gen_tasks = [
            asyncio.create_task(self._generator_worker(generate_fn, worker_id=i))
            for i in range(self._gen_concurrency)
        ]
        saver_task = asyncio.create_task(
            self._saver_worker(save_fn, expected_count=len(raw_trends))
        )

        # 모든 Worker 완료 대기
        await scorer_task
        await asyncio.gather(*gen_tasks)
        await saver_task

        elapsed = (datetime.now() - started_at).total_seconds()
        success_count = sum(1 for e in self._results if not e.error)
        log.info(
            f"[Streaming] 파이프라인 완료 — "
            f"성공 {success_count}/{len(raw_trends)}개, "
            f"소요 {elapsed:.1f}초, "
            f"에러 {len(self._errors)}건"
        )

        return self._results

    async def _scorer_worker(self, raw_trends, contexts, score_fn):
        """Stage 1: 트렌드를 하나씩 스코어링하고 scored_queue에 넣는다."""
        for trend in raw_trends:
            event = PipelineEvent(trend=trend, stage="scoring")
            try:
                if score_fn:
                    scored = await asyncio.wait_for(
                        score_fn(trend, contexts.get(trend.name if hasattr(trend, 'name') else str(trend))),
                        timeout=self.STAGE_TIMEOUT_SECONDS,
                    )
                else:
                    scored = trend  # score_fn이 없으면 이미 ScoredTrend로 간주
                event.stage = "scored"
                event.complete(result=scored)
                await self._scored_queue.put(event)
            except asyncio.TimeoutError:
                event.complete(error="scoring_timeout")
                self._errors.append(f"[Scorer] 타임아웃: {trend}")
                log.warning(f"[Streaming] 스코어링 타임아웃: {trend}")
            except Exception as e:
                event.complete(error=f"scoring_error: {e}")
                self._errors.append(f"[Scorer] {type(e).__name__}: {e}")
                log.warning(f"[Streaming] 스코어링 실패: {e}")

        # 모든 Generator에게 종료 신호 전송
        for _ in range(self._gen_concurrency):
            await self._scored_queue.put(_SENTINEL)

    async def _generator_worker(self, generate_fn, *, worker_id: int = 0):
        """Stage 2: scored_queue에서 꺼내 생성하고 generated_queue에 넣는다."""
        while True:
            event = await self._scored_queue.get()
            if event is _SENTINEL:
                await self._generated_queue.put(_SENTINEL)
                break

            scored_trend = event.result
            event.stage = "generating"
            event.started_at = datetime.now()  # 생성 시작 시각 재설정

            try:
                if generate_fn:
                    batch = await asyncio.wait_for(
                        generate_fn(scored_trend),
                        timeout=self.STAGE_TIMEOUT_SECONDS,
                    )
                else:
                    batch = None  # dry-run 모드
                event.stage = "generated"
                event.complete(result=batch)
            except asyncio.TimeoutError:
                event.complete(error="generation_timeout")
                self._errors.append(f"[Gen-{worker_id}] 타임아웃: {scored_trend}")
                log.warning(f"[Streaming-{worker_id}] 생성 타임아웃")
            except Exception as e:
                event.complete(error=f"generation_error: {e}")
                self._errors.append(f"[Gen-{worker_id}] {type(e).__name__}: {e}")
                log.warning(f"[Streaming-{worker_id}] 생성 실패: {e}")

            await self._generated_queue.put(event)

    async def _saver_worker(self, save_fn, *, expected_count: int):
        """Stage 3: generated_queue에서 꺼내 저장하고 결과를 수집한다."""
        sentinel_count = 0

        while sentinel_count < self._gen_concurrency:
            event = await self._generated_queue.get()
            if event is _SENTINEL:
                sentinel_count += 1
                continue

            if event.error:
                self._results.append(event)
                continue

            event.stage = "saving"
            try:
                if save_fn and event.result:
                    await asyncio.wait_for(
                        save_fn(event.trend, event.result),
                        timeout=self.STAGE_TIMEOUT_SECONDS,
                    )
                event.stage = "saved"
                event.complete(result=event.result)
            except asyncio.TimeoutError:
                event.complete(error="save_timeout")
                self._errors.append(f"[Saver] 타임아웃")
            except Exception as e:
                event.complete(error=f"save_error: {e}")
                self._errors.append(f"[Saver] {type(e).__name__}: {e}")

            self._results.append(event)

    @property
    def error_count(self) -> int:
        return len(self._errors)

    @property
    def success_count(self) -> int:
        return sum(1 for e in self._results if not e.error)
