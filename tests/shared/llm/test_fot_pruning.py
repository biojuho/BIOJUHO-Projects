"""Tests for FoT pruning (ToT-inspired) in shared.llm.reasoning.forest_of_thought."""

import pytest

from shared.llm.reasoning.forest_of_thought import (
    ForestOfThoughtEngine,
    FoTSubtaskResult,
)


class TestFoTPruning:
    """Test the ToT-inspired pruning logic in ForestOfThoughtEngine."""

    def test_quality_check_passes_good_result(self):
        result = FoTSubtaskResult(
            subtask="API 엔드포인트 설계",
            text="REST API는 다음과 같이 설계합니다. GET /api/v1/trends, POST /api/v1/reports 등의 엔드포인트를 구성하며, 각 엔드포인트는 적절한 인증 미들웨어를 거칩니다.",
        )
        assert ForestOfThoughtEngine._quality_check(result) is True

    def test_quality_check_rejects_short_result(self):
        result = FoTSubtaskResult(
            subtask="DB 스키마",
            text="OK",
        )
        assert ForestOfThoughtEngine._quality_check(result) is False

    def test_quality_check_rejects_empty_result(self):
        result = FoTSubtaskResult(
            subtask="인증 모듈",
            text="   ",
        )
        assert ForestOfThoughtEngine._quality_check(result) is False

    def test_quality_check_rejects_error_dominated(self):
        result = FoTSubtaskResult(
            subtask="배포 스크립트",
            text="error failed exception cannot traceback",
        )
        assert ForestOfThoughtEngine._quality_check(result) is False

    def test_quality_check_passes_error_mention_in_context(self):
        """A result that mentions 'error' in context but isn't error-dominated."""
        result = FoTSubtaskResult(
            subtask="에러 핸들링 설계",
            text="에러 핸들링은 다음과 같이 구현합니다. 1) 전역 에러 바운더리를 설정하여 "
                 "예외를 캡처합니다. 2) 각 모듈에서 try-except 블록으로 개별 에러를 처리합니다. "
                 "3) 에러 로그를 Notion 데이터베이스에 기록합니다. 4) 심각한 에러의 경우 "
                 "Discord 웹훅으로 알림을 전송합니다.",
        )
        # Should pass because error words are contextual, not indicating failure
        assert ForestOfThoughtEngine._quality_check(result) is True

    def test_quality_check_boundary_length(self):
        """Result exactly at the minimum quality length."""
        # _MIN_QUALITY_LENGTH = 50
        result = FoTSubtaskResult(
            subtask="간단한 설정",
            text="x" * 49,  # just under threshold
        )
        assert ForestOfThoughtEngine._quality_check(result) is False

        result_ok = FoTSubtaskResult(
            subtask="간단한 설정",
            text="x" * 50,  # exactly at threshold
        )
        assert ForestOfThoughtEngine._quality_check(result_ok) is True

    def test_quality_check_korean_error_indicators(self):
        """Test pruning with Korean error indicators."""
        result = FoTSubtaskResult(
            subtask="DB 연결",
            text="실패 에러 불가능 할 수 없",
        )
        assert ForestOfThoughtEngine._quality_check(result) is False
