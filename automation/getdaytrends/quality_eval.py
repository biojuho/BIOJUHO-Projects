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

import os
from dataclasses import dataclass, field

from loguru import logger as log


def _deepeval_runtime_disabled() -> bool:
    """Allow tests / offline environments to skip DeepEval LLM probes.

    Each DeepEval metric (Hallucination / Faithfulness / AnswerRelevancy)
    attempts a real LLM call. When no LLM key is configured the SDK still
    spends 5-15s per metric on init/timeout before falling back. Tests that
    only exercise the rule-based fact_checker path don't need this overhead.
    """
    return os.getenv("DEEPEVAL_DISABLED", "").lower() in {"1", "true", "yes"}

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
    """Evaluate generated content with DeepEval metrics when available."""
    if not DEEPEVAL_AVAILABLE or _deepeval_runtime_disabled():
        return EvalResult()
    if not generated_text or not source_context:
        return EvalResult()

    try:
        test_case = LLMTestCase(
            input=f"Trend keyword '{keyword}' content generation",
            actual_output=generated_text,
            retrieval_context=[source_context],
        )
        result = EvalResult()
        _apply_deepeval_metric(
            result,
            HallucinationMetric(threshold=hallucination_threshold),
            test_case,
            score_field="hallucination_score",
            detail_key="hallucination_reason",
            issue_template="hallucination detected (score={score:.2f}, threshold={threshold})",
            threshold=hallucination_threshold,
            debug_label="hallucination",
        )
        _apply_deepeval_metric(
            result,
            FaithfulnessMetric(threshold=faithfulness_threshold),
            test_case,
            score_field="faithfulness_score",
            detail_key="faithfulness_reason",
            issue_template="faithfulness mismatch (score={score:.2f}, threshold={threshold})",
            threshold=faithfulness_threshold,
            debug_label="faithfulness",
        )
        _apply_deepeval_metric(
            result,
            AnswerRelevancyMetric(threshold=relevancy_threshold),
            test_case,
            score_field="relevancy_score",
            detail_key="relevancy_reason",
            issue_template="relevancy too low (score={score:.2f}, threshold={threshold})",
            threshold=relevancy_threshold,
            debug_label="relevancy",
        )
    except Exception as e:
        log.warning(f"[DeepEval] evaluation failed: {type(e).__name__}: {e}")
        return EvalResult()

    _log_eval_issues(keyword, result)
    return result


def _apply_deepeval_metric(
    result: EvalResult,
    metric,
    test_case,
    *,
    score_field: str,
    detail_key: str,
    issue_template: str,
    threshold: float,
    debug_label: str,
) -> None:
    try:
        metric.measure(test_case)
        score = metric.score or 0.0
        setattr(result, score_field, score)
        if not metric.is_successful():
            result.issues.append(issue_template.format(score=score, threshold=threshold))
            result.passed = False
        result.details[detail_key] = metric.reason
    except Exception as e:
        log.debug(f"[DeepEval] {debug_label} metric failed: {e}")


def _log_eval_issues(keyword: str, result: EvalResult) -> None:
    if not result.issues:
        return
    log.info(
        f"[DeepEval] '{keyword}' quality issues {len(result.issues)}: "
        f"H={result.hallucination_score:.2f} "
        f"F={result.faithfulness_score:.2f} "
        f"R={result.relevancy_score:.2f}"
    )

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
