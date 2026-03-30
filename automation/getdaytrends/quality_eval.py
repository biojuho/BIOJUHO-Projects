"""
getdaytrends — DeepEval 기반 LLM 출력 품질 자동 평가 모듈.

기존 fact_checker.py의 규칙 기반 검증을 보완하여 LLM 기반 자동 평가를 수행:
1. 환각 탐지 (Hallucination): 소스에 없는 정보 생성 여부
2. 답변 관련성 (Relevance): 트렌드 키워드/컨텍스트와의 일치도
3. 사실 일관성 (Faithfulness): 소스 데이터와의 사실 일관성

Usage:
    from quality_eval import evaluate_content, EvalResult
    result = evaluate_content(
        generated_text="생성된 트윗",
        source_context="수집된 컨텍스트",
        keyword="트렌드 키워드",
    )
    if not result.passed:
        print(result.issues)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from loguru import logger as log

# DeepEval 선택 의존성
try:
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        FaithfulnessMetric,
        HallucinationMetric,
    )
    from deepeval.test_case import LLMTestCase

    DEEPEVAL_AVAILABLE = True
except ImportError:
    DEEPEVAL_AVAILABLE = False


@dataclass
class EvalResult:
    """품질 평가 결과."""

    passed: bool = True
    hallucination_score: float = 1.0  # 0=환각 없음, 1=전부 환각
    faithfulness_score: float = 1.0  # 0=불일치, 1=완전 일치
    relevancy_score: float = 1.0  # 0=무관, 1=완전 관련
    issues: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)


# ══════════════════════════════════════════════════════
#  DeepEval 기반 평가
# ══════════════════════════════════════════════════════


def evaluate_content(
    generated_text: str,
    source_context: str,
    keyword: str,
    *,
    hallucination_threshold: float = 0.5,
    faithfulness_threshold: float = 0.6,
    relevancy_threshold: float = 0.5,
) -> EvalResult:
    """
    생성된 콘텐츠를 DeepEval 메트릭으로 평가.
    DeepEval 미설치 시 기본 통과 반환 (기존 동작 호환).

    Args:
        generated_text: 평가할 생성 콘텐츠
        source_context: 소스 컨텍스트 (뉴스, X, Reddit)
        keyword: 트렌드 키워드
        hallucination_threshold: 환각 점수 기각 임계값 (높을수록 관대)
        faithfulness_threshold: 사실 일관성 기각 임계값 (높을수록 엄격)
        relevancy_threshold: 관련성 기각 임계값 (높을수록 엄격)
    """
    if not DEEPEVAL_AVAILABLE:
        return EvalResult()

    if not generated_text or not source_context:
        return EvalResult()

    result = EvalResult()

    try:
        test_case = LLMTestCase(
            input=f"트렌드 키워드 '{keyword}'에 대한 SNS 콘텐츠를 생성하세요.",
            actual_output=generated_text,
            retrieval_context=[source_context],
        )

        # 1. 환각 탐지
        try:
            hallucination_metric = HallucinationMetric(
                threshold=hallucination_threshold,
            )
            hallucination_metric.measure(test_case)
            result.hallucination_score = hallucination_metric.score or 0.0
            if not hallucination_metric.is_successful():
                result.issues.append(
                    f"환각 감지 (score={result.hallucination_score:.2f}, " f"threshold={hallucination_threshold})"
                )
                result.passed = False
            result.details["hallucination_reason"] = hallucination_metric.reason
        except Exception as e:
            log.debug(f"[DeepEval] 환각 평가 실패: {e}")

        # 2. 사실 일관성
        try:
            faithfulness_metric = FaithfulnessMetric(
                threshold=faithfulness_threshold,
            )
            faithfulness_metric.measure(test_case)
            result.faithfulness_score = faithfulness_metric.score or 0.0
            if not faithfulness_metric.is_successful():
                result.issues.append(
                    f"사실 불일치 (score={result.faithfulness_score:.2f}, " f"threshold={faithfulness_threshold})"
                )
                result.passed = False
            result.details["faithfulness_reason"] = faithfulness_metric.reason
        except Exception as e:
            log.debug(f"[DeepEval] 사실 일관성 평가 실패: {e}")

        # 3. 답변 관련성
        try:
            relevancy_metric = AnswerRelevancyMetric(
                threshold=relevancy_threshold,
            )
            relevancy_metric.measure(test_case)
            result.relevancy_score = relevancy_metric.score or 0.0
            if not relevancy_metric.is_successful():
                result.issues.append(
                    f"관련성 부족 (score={result.relevancy_score:.2f}, " f"threshold={relevancy_threshold})"
                )
                result.passed = False
            result.details["relevancy_reason"] = relevancy_metric.reason
        except Exception as e:
            log.debug(f"[DeepEval] 관련성 평가 실패: {e}")

    except Exception as e:
        log.warning(f"[DeepEval] 평가 실패: {type(e).__name__}: {e}")
        return EvalResult()  # 실패 시 기본 통과

    if result.issues:
        log.info(
            f"[DeepEval] '{keyword}' 품질 이슈 {len(result.issues)}건: "
            f"H={result.hallucination_score:.2f} "
            f"F={result.faithfulness_score:.2f} "
            f"R={result.relevancy_score:.2f}"
        )

    return result


# ══════════════════════════════════════════════════════
#  배치 평가 (파이프라인 통합용)
# ══════════════════════════════════════════════════════


def evaluate_batch(
    tweets: list[str],
    source_context: str,
    keyword: str,
    **kwargs,
) -> list[EvalResult]:
    """여러 트윗을 한 번에 평가."""
    return [evaluate_content(tweet, source_context, keyword, **kwargs) for tweet in tweets]


def batch_pass_rate(results: list[EvalResult]) -> float:
    """배치 평가 통과율 (0.0 ~ 1.0)."""
    if not results:
        return 1.0
    return sum(1 for r in results if r.passed) / len(results)
