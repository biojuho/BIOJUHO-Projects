"""quality_eval.py 테스트 — DeepEval 품질 평가 모듈."""

import pytest

from quality_eval import (
    DEEPEVAL_AVAILABLE,
    EvalResult,
    batch_pass_rate,
)


class TestEvalResult:
    """EvalResult 데이터 클래스 테스트."""

    def test_default_passed(self):
        result = EvalResult()
        assert result.passed is True
        assert result.issues == []

    def test_failed_with_issues(self):
        result = EvalResult(
            passed=False,
            hallucination_score=0.8,
            issues=["환각 감지 (score=0.80)"],
        )
        assert result.passed is False
        assert len(result.issues) == 1


class TestBatchPassRate:
    """배치 통과율 계산 테스트."""

    def test_all_passed(self):
        results = [EvalResult(passed=True), EvalResult(passed=True)]
        assert batch_pass_rate(results) == 1.0

    def test_half_failed(self):
        results = [EvalResult(passed=True), EvalResult(passed=False)]
        assert batch_pass_rate(results) == 0.5

    def test_all_failed(self):
        results = [EvalResult(passed=False), EvalResult(passed=False)]
        assert batch_pass_rate(results) == 0.0

    def test_empty(self):
        assert batch_pass_rate([]) == 1.0


class TestEvaluateContentIntegration:
    """evaluate_content 통합 테스트 (DeepEval 설치 여부에 따라 동작)."""

    def test_empty_text_returns_default(self):
        from quality_eval import evaluate_content

        result = evaluate_content("", "source context", "keyword")
        assert result.passed is True

    def test_empty_context_returns_default(self):
        from quality_eval import evaluate_content

        result = evaluate_content("generated text", "", "keyword")
        assert result.passed is True

    @pytest.mark.integration
    @pytest.mark.skipif(not DEEPEVAL_AVAILABLE, reason="DeepEval 미설치")
    def test_basic_evaluation(self):
        """DeepEval이 설치된 경우 기본 평가 동작 확인."""
        from quality_eval import evaluate_content

        result = evaluate_content(
            "삼성전자 주가가 10% 상승했다",
            "삼성전자 주가 10% 상승 보도",
            "삼성전자",
        )
        assert isinstance(result, EvalResult)
        # LLM-based scores are non-deterministic; verify valid range only
        assert 0.0 <= result.hallucination_score <= 1.0
        assert 0.0 <= result.faithfulness_score <= 1.0
