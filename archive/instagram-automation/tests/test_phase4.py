"""Tests for Phase 4: AI Self-Critique loop and Reels auto-creation."""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ---- ContentCritique Tests ----


class TestCritiqueResult:
    def test_from_dict_passing(self):
        from services.content_critique import CritiqueResult

        data = {
            "scores": {
                "engagement": 8,
                "clarity": 9,
                "hook": 7,
                "cta": 8,
                "authenticity": 8,
            },
            "average": 8.0,
            "strengths": ["Good hook"],
            "weaknesses": [],
            "suggestions": [],
        }
        result = CritiqueResult.from_dict(data, threshold=7.0)
        assert result.passed is True
        assert result.average == 8.0
        assert len(result.scores) == 5

    def test_from_dict_failing(self):
        from services.content_critique import CritiqueResult

        data = {
            "scores": {
                "engagement": 5,
                "clarity": 6,
                "hook": 4,
                "cta": 5,
                "authenticity": 6,
            },
            "average": 5.2,
            "weaknesses": ["Weak hook"],
            "suggestions": ["Add stronger opening"],
        }
        result = CritiqueResult.from_dict(data, threshold=7.0)
        assert result.passed is False
        assert result.average == 5.2

    def test_average_recalculation(self):
        from services.content_critique import CritiqueResult

        data = {
            "scores": {"a": 10, "b": 10, "c": 10},
            "average": 5.0,  # Wrong average — should be recalculated
        }
        result = CritiqueResult.from_dict(data)
        assert result.average == 10.0

    def test_empty_scores(self):
        from services.content_critique import CritiqueResult

        result = CritiqueResult.from_dict({})
        assert result.average == 0.0
        assert result.passed is False


class TestCritiqueLoopResult:
    def test_basic(self):
        from services.content_critique import CritiqueLoopResult

        result = CritiqueLoopResult(
            final_caption="Test caption",
            revisions=1,
            passed=True,
        )
        assert result.final_caption == "Test caption"
        assert result.revisions == 1
        assert result.passed is True


class TestContentCritiqueAxes:
    def test_score_axes_defined(self):
        from services.content_critique import ContentCritique

        assert len(ContentCritique.SCORE_AXES) == 5
        assert "engagement" in ContentCritique.SCORE_AXES
        assert "authenticity" in ContentCritique.SCORE_AXES


# ---- ReelsScript Tests ----


class TestReelsScript:
    def test_from_dict(self):
        from services.reels_generator import ReelsScript

        data = {
            "hook": "알고 계셨나요?",
            "body": ["포인트1", "포인트2", "포인트3"],
            "cta": "팔로우하세요!",
            "full_script": "전체 대본 텍스트",
            "estimated_duration": 45,
        }
        script = ReelsScript.from_dict(data)
        assert script.hook == "알고 계셨나요?"
        assert len(script.body) == 3
        assert script.estimated_duration == 45

    def test_from_dict_defaults(self):
        from services.reels_generator import ReelsScript

        script = ReelsScript.from_dict({})
        assert script.hook == ""
        assert script.estimated_duration == 45


class TestSRTEntry:
    def test_to_srt(self):
        from services.reels_generator import SRTEntry

        entry = SRTEntry(
            index=1,
            start_time="00:00:00,000",
            end_time="00:00:05,000",
            text="Hello World",
        )
        srt = entry.to_srt()
        assert "1\n" in srt
        assert "00:00:00,000 --> 00:00:05,000" in srt
        assert "Hello World" in srt


class TestTimeFormat:
    def test_format_zero(self):
        from services.reels_generator import ReelsGenerator

        assert ReelsGenerator._format_time(0) == "00:00:00,000"

    def test_format_seconds(self):
        from services.reels_generator import ReelsGenerator

        assert ReelsGenerator._format_time(5.5) == "00:00:05,500"

    def test_format_minutes(self):
        from services.reels_generator import ReelsGenerator

        assert ReelsGenerator._format_time(75.0) == "00:01:15,000"


class TestSRTGeneration:
    def test_generate_srt(self):
        from services.reels_generator import ReelsGenerator, ReelsScript

        gen = ReelsGenerator.__new__(ReelsGenerator)
        script = ReelsScript(
            hook="알고 계셨나요?",
            body=["포인트1", "포인트2", "포인트3"],
            cta="팔로우하세요!",
            estimated_duration=45,
        )
        with tempfile.NamedTemporaryFile(suffix=".srt", delete=False) as f:
            path = gen.generate_srt(script, f.name)
            content = path.read_text(encoding="utf-8")

        assert "1\n" in content
        assert "알고 계셨나요?" in content
        assert "팔로우하세요!" in content
        # Should have 5 entries (hook + 3 body + cta)
        assert content.count("-->") == 5

    def test_generate_srt_empty_script(self):
        from services.reels_generator import ReelsGenerator, ReelsScript

        gen = ReelsGenerator.__new__(ReelsGenerator)
        script = ReelsScript(estimated_duration=30)
        with tempfile.NamedTemporaryFile(suffix=".srt", delete=False) as f:
            path = gen.generate_srt(script, f.name)
            content = path.read_text(encoding="utf-8")
        # No entries
        assert content.strip() == ""


class TestReelResult:
    def test_success(self):
        from services.reels_generator import ReelResult, ReelsScript

        result = ReelResult(
            script=ReelsScript(full_script="test"),
            audio_path="/tmp/test.mp3",
            srt_path="/tmp/test.srt",
            success=True,
        )
        assert result.success is True

    def test_failure(self):
        from services.reels_generator import ReelResult, ReelsScript

        result = ReelResult(
            script=ReelsScript(), error="TTS failed"
        )
        assert result.success is False
        assert "TTS" in result.error
