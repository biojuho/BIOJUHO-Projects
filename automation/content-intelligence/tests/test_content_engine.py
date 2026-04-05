"""CIE content_engine 단위 테스트 — _safe_int, _parse_pro_qa, _build_persona_qa_context."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

_CIE_DIR = Path(__file__).resolve().parents[1]
if str(_CIE_DIR) not in sys.path:
    sys.path.insert(0, str(_CIE_DIR))

from generators.content_engine import (
    _build_persona_qa_context,
    _parse_pro_qa,
    _safe_int,
)
from storage.models import QAReport


# ─── _safe_int ────────────────────────────────────


class TestSafeInt:
    def test_normal_int(self):
        assert _safe_int(15, 20) == 15

    def test_string_int(self):
        assert _safe_int("12", 20) == 12

    def test_above_cap(self):
        assert _safe_int(25, 20) == 20

    def test_below_zero(self):
        assert _safe_int(-5, 20) == 0

    def test_none(self):
        assert _safe_int(None, 20) == 0

    def test_fraction_string(self):
        assert _safe_int("15/20", 20) == 15

    def test_tilde_prefix(self):
        assert _safe_int("~15", 20) == 15

    def test_garbage_string(self):
        assert _safe_int("excellent", 20) == 0

    def test_float_value(self):
        assert _safe_int(14.7, 20) == 14

    def test_empty_string(self):
        assert _safe_int("", 20) == 0

    def test_zero_cap(self):
        assert _safe_int(5, 0) == 0


# ─── _build_persona_qa_context ────────────────────


class TestBuildPersonaQAContext:
    def test_none_personas(self):
        assert _build_persona_qa_context(None) == ""

    def test_empty_personas(self):
        assert _build_persona_qa_context([]) == ""

    def test_single_persona(self):
        personas = [
            {
                "id": "early_adopter",
                "name": "얼리어답터",
                "pain_points": ["정보 부족", "시간 낭비"],
            }
        ]
        result = _build_persona_qa_context(personas)
        assert "early_adopter" in result
        assert "얼리어답터" in result
        assert "정보 부족" in result

    def test_multiple_personas(self):
        personas = [
            {"id": "a", "name": "A", "pain_points": ["p1"]},
            {"id": "b", "name": "B", "pain_points": ["p2"]},
        ]
        result = _build_persona_qa_context(personas)
        assert "a" in result
        assert "b" in result


# ─── _parse_pro_qa ────────────────────────────────


class TestParseProQA:
    class _FakeConfig:
        qa_min_score = 70

    def test_flat_scores(self):
        data = {
            "scores": {
                "hook": 16, "fact": 12, "tone": 11,
                "kick": 10, "angle": 10,
                "regulation": 8, "algorithm": 7,
                "reader_value": 7, "originality": 6, "credibility": 5,
            },
            "diagnostics": {},
            "persona_fits": [],
            "warnings": [],
            "rewrite_suggestion": "",
        }
        qa = _parse_pro_qa(data, self._FakeConfig())
        assert isinstance(qa, QAReport)
        assert qa.hook_score == 16
        assert qa.total_score == 16 + 12 + 11 + 10 + 10 + 8 + 7
        assert qa.reader_value_score == 7

    def test_nested_scores_fallback(self):
        """scores 키가 없으면 data 자체에서 점수를 읽는다."""
        data = {
            "hook": 15, "fact": 10, "tone": 10,
            "kick": 10, "angle": 10,
            "regulation": 8, "algorithm": 7,
            "reader_value": 5, "originality": 4, "credibility": 3,
        }
        qa = _parse_pro_qa(data, self._FakeConfig())
        assert qa.hook_score == 15

    def test_diagnostics_parsed(self):
        data = {
            "scores": {
                "hook": 5, "fact": 12, "tone": 10,
                "kick": 10, "angle": 10,
                "regulation": 8, "algorithm": 7,
                "reader_value": 5, "originality": 5, "credibility": 5,
            },
            "diagnostics": {
                "hook": {"reason": "weak opening", "suggestion": "add data"},
                "fact": {"reason": "ok", "suggestion": ""},
            },
            "persona_fits": [],
            "warnings": ["tone mismatch"],
            "rewrite_suggestion": "focus on hook",
        }
        qa = _parse_pro_qa(data, self._FakeConfig())
        assert len(qa.diagnostics) == 10  # all 10 axes
        hook_diag = next(d for d in qa.diagnostics if d.axis == "hook")
        assert hook_diag.reason == "weak opening"
        assert hook_diag.suggestion == "add data"
        assert qa.rewrite_suggestion == "focus on hook"

    def test_persona_fits_parsed(self):
        data = {
            "scores": {
                "hook": 15, "fact": 12, "tone": 10,
                "kick": 10, "angle": 10,
                "regulation": 8, "algorithm": 7,
                "reader_value": 5, "originality": 5, "credibility": 5,
            },
            "diagnostics": {},
            "persona_fits": [
                {"persona_id": "early_adopter", "persona_name": "EA", "fit_score": 8, "reason": "good match"},
                {"persona_id": "practitioner", "fit_score": 6, "reason": "moderate"},
            ],
            "warnings": [],
            "rewrite_suggestion": "",
        }
        qa = _parse_pro_qa(data, self._FakeConfig())
        assert len(qa.persona_fits) == 2
        assert qa.persona_fits[0].fit_score == 8
        # persona_name fallback to persona_id when persona_name not present
        assert qa.persona_fits[1].persona_name == "practitioner"

    def test_invalid_score_clamped(self):
        data = {
            "scores": {
                "hook": 99, "fact": -5, "tone": "~18",
                "kick": None, "angle": "bad",
                "regulation": 8, "algorithm": 7,
                "reader_value": 5, "originality": 5, "credibility": 5,
            },
            "diagnostics": {},
            "persona_fits": [],
            "warnings": [],
            "rewrite_suggestion": "",
        }
        qa = _parse_pro_qa(data, self._FakeConfig())
        assert qa.hook_score == 20     # clamped to max 20
        assert qa.fact_score == 0      # clamped to min 0
        assert qa.tone_score == 15     # "~18" -> 18, clamped to 15
        assert qa.kick_score == 0      # None -> 0
        assert qa.angle_score == 0     # "bad" -> 0

    def test_applied_min_score(self):
        data = {
            "scores": {
                "hook": 10, "fact": 10, "tone": 10,
                "kick": 10, "angle": 10,
                "regulation": 5, "algorithm": 5,
                "reader_value": 5, "originality": 5, "credibility": 5,
            },
            "diagnostics": {},
            "persona_fits": [],
            "warnings": [],
        }
        qa = _parse_pro_qa(data, self._FakeConfig())
        assert qa.applied_min_score == 70
