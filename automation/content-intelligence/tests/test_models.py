"""CIE 데이터 모델 단위 테스트."""

from __future__ import annotations

from datetime import datetime

import pytest

import sys
from pathlib import Path

_CIE_DIR = Path(__file__).resolve().parents[1]
if str(_CIE_DIR) not in sys.path:
    sys.path.insert(0, str(_CIE_DIR))

from storage.models import (
    ContentBatch,
    GeneratedContent,
    MergedTrendReport,
    MonthlyReview,
    PersonaFitScore,
    PlatformTrend,
    PlatformTrendReport,
    PublishResult,
    QAAxisDiagnostic,
    QAReport,
    RegulationReport,
    ThreadPost,
    UnifiedChecklist,
)


# ─── QAAxisDiagnostic ─────────────────────────────


class TestQAAxisDiagnostic:
    def test_score_ratio_normal(self):
        d = QAAxisDiagnostic(axis="hook", score=10, max_score=20)
        assert d.score_ratio == 0.5

    def test_score_ratio_zero_max(self):
        d = QAAxisDiagnostic(axis="hook", score=5, max_score=0)
        assert d.score_ratio == 0.0

    def test_is_weak_below_50(self):
        d = QAAxisDiagnostic(axis="fact", score=3, max_score=15)
        assert d.is_weak is True  # 3/15 = 0.2

    def test_is_weak_at_50(self):
        d = QAAxisDiagnostic(axis="fact", score=10, max_score=20)
        assert d.is_weak is False  # 10/20 = 0.5 -> not < 0.5

    def test_is_weak_above_50(self):
        d = QAAxisDiagnostic(axis="tone", score=12, max_score=15)
        assert d.is_weak is False


# ─── PersonaFitScore ──────────────────────────────


class TestPersonaFitScore:
    def test_default_values(self):
        p = PersonaFitScore(persona_id="early_adopter", persona_name="Early Adopter")
        assert p.fit_score == 0
        assert p.reason == ""

    def test_custom_values(self):
        p = PersonaFitScore(
            persona_id="practitioner",
            persona_name="실무자",
            fit_score=8,
            reason="실무 적용 사례 풍부",
        )
        assert p.fit_score == 8


# ─── QAReport ─────────────────────────────────────


class TestQAReport:
    def _make_report(self, **overrides) -> QAReport:
        defaults = dict(
            hook_score=15,
            fact_score=12,
            tone_score=10,
            kick_score=10,
            angle_score=10,
            regulation_score=8,
            algorithm_score=7,
        )
        defaults.update(overrides)
        return QAReport(**defaults)

    def test_total_score(self):
        r = self._make_report()
        assert r.total_score == 15 + 12 + 10 + 10 + 10 + 8 + 7  # 72

    def test_passes_above_threshold(self):
        r = self._make_report()
        assert r.passes(70) is True

    def test_passes_below_threshold(self):
        r = self._make_report()
        assert r.passes(80) is False

    def test_pass_threshold_property(self):
        r = self._make_report(applied_min_score=70)
        assert r.pass_threshold is True

    def test_pass_threshold_fail(self):
        r = self._make_report(applied_min_score=80)
        assert r.pass_threshold is False

    def test_weak_axes_returns_weak_only(self):
        diags = [
            QAAxisDiagnostic(axis="hook", score=5, max_score=20),   # weak (0.25)
            QAAxisDiagnostic(axis="fact", score=12, max_score=15),  # ok (0.8)
            QAAxisDiagnostic(axis="tone", score=3, max_score=15),   # weak (0.2)
        ]
        r = self._make_report(diagnostics=diags)
        weak = r.weak_axes
        assert len(weak) == 2
        assert {d.axis for d in weak} == {"hook", "tone"}

    def test_top_persona_returns_highest(self):
        fits = [
            PersonaFitScore(persona_id="a", persona_name="A", fit_score=5),
            PersonaFitScore(persona_id="b", persona_name="B", fit_score=9),
            PersonaFitScore(persona_id="c", persona_name="C", fit_score=7),
        ]
        r = self._make_report(persona_fits=fits)
        assert r.top_persona.persona_id == "b"

    def test_top_persona_none_when_empty(self):
        r = self._make_report()
        assert r.top_persona is None

    def test_to_retry_feedback_with_diagnostics(self):
        diags = [
            QAAxisDiagnostic(
                axis="hook", score=3, max_score=20,
                reason="첫 문장 평이함", suggestion="숫자로 시작",
            ),
            QAAxisDiagnostic(axis="fact", score=12, max_score=15),  # ok
        ]
        r = self._make_report(diagnostics=diags)
        feedback = r.to_retry_feedback()
        assert "hook" in feedback
        assert "숫자로 시작" in feedback

    def test_to_retry_feedback_fallback_warnings(self):
        r = self._make_report(warnings=["톤 불일치", "키워드 누락"])
        feedback = r.to_retry_feedback()
        assert "톤 불일치" in feedback

    def test_to_emoji_report_pass(self):
        r = self._make_report(applied_min_score=70)
        report = r.to_emoji_report()
        assert "PASS" in report
        assert "Hook:" in report

    def test_to_emoji_report_fail(self):
        r = self._make_report(
            hook_score=5, fact_score=5, tone_score=5,
            kick_score=5, angle_score=5,
            regulation_score=3, algorithm_score=2,
            applied_min_score=70,
        )
        report = r.to_emoji_report()
        assert "FAIL" in report

    def test_to_emoji_report_includes_supplementary(self):
        r = self._make_report(
            reader_value_score=8, originality_score=6, credibility_score=7,
        )
        report = r.to_emoji_report()
        assert "RV: 8/10" in report
        assert "Orig: 6/10" in report


# ─── ThreadPost ───────────────────────────────────


class TestThreadPost:
    def test_defaults(self):
        tp = ThreadPost()
        assert tp.role == "body"
        assert tp.char_count == 0

    def test_custom(self):
        tp = ThreadPost(index=0, role="hook", body="test", char_count=4)
        assert tp.role == "hook"


# ─── GeneratedContent ─────────────────────────────


class TestGeneratedContent:
    def test_qa_passed_none(self):
        c = GeneratedContent(platform="x", content_type="post")
        assert c.qa_passed is False

    def test_qa_passed_pass(self):
        qa = QAReport(
            hook_score=18, fact_score=14, tone_score=13,
            kick_score=12, angle_score=12, regulation_score=9,
            algorithm_score=8, applied_min_score=70,
        )
        c = GeneratedContent(platform="x", content_type="post", qa_report=qa)
        assert c.qa_passed is True

    def test_is_published(self):
        c = GeneratedContent(platform="x", content_type="post")
        assert c.is_published is False
        c.published_at = datetime.now()
        assert c.is_published is True

    def test_is_thread(self):
        c = GeneratedContent(
            platform="x", content_type="x_thread",
            thread_posts=[ThreadPost(index=0, role="hook", body="test")],
        )
        assert c.is_thread is True

    def test_is_not_thread_wrong_type(self):
        c = GeneratedContent(
            platform="x", content_type="post",
            thread_posts=[ThreadPost(index=0)],
        )
        assert c.is_thread is False

    def test_thread_summary_for_thread(self):
        posts = [
            ThreadPost(index=0, role="hook", body="Hook line here"),
            ThreadPost(index=1, role="body", body="Body content here"),
        ]
        c = GeneratedContent(platform="x", content_type="x_thread", thread_posts=posts)
        summary = c.thread_summary
        assert "[hook]" in summary
        assert "[body]" in summary

    def test_thread_summary_for_non_thread(self):
        c = GeneratedContent(platform="x", content_type="post", body="Some content body text")
        summary = c.thread_summary
        assert summary == "Some content body text"


# ─── ContentBatch ─────────────────────────────────


class TestContentBatch:
    def test_all_passed_true(self):
        qa = QAReport(
            hook_score=18, fact_score=14, tone_score=13,
            kick_score=12, angle_score=12, regulation_score=9,
            algorithm_score=8, applied_min_score=70,
        )
        contents = [
            GeneratedContent(platform="x", content_type="post", qa_report=qa),
        ]
        batch = ContentBatch(contents=contents)
        assert batch.all_passed is True

    def test_all_passed_false(self):
        qa_fail = QAReport(
            hook_score=5, fact_score=5, tone_score=5,
            kick_score=5, angle_score=5, regulation_score=3,
            algorithm_score=2, applied_min_score=70,
        )
        contents = [
            GeneratedContent(platform="x", content_type="post", qa_report=qa_fail),
        ]
        batch = ContentBatch(contents=contents)
        assert batch.all_passed is False

    def test_summary(self):
        qa = QAReport(
            hook_score=15, fact_score=10, tone_score=10,
            kick_score=10, angle_score=10, regulation_score=8,
            algorithm_score=7,
        )
        contents = [
            GeneratedContent(platform="x", content_type="post", qa_report=qa),
            GeneratedContent(platform="naver", content_type="blog", qa_report=qa),
        ]
        batch = ContentBatch(contents=contents)
        s = batch.summary()
        assert "2건" in s
        assert "naver" in s or "x" in s


# ─── MergedTrendReport ────────────────────────────


class TestMergedTrendReport:
    def test_to_summary_text_basic(self):
        trend = PlatformTrend(keyword="AI Agent", volume=100, format_trend="thread", tone_trend="analytical")
        report = PlatformTrendReport(platform="x", trends=[trend])
        merged = MergedTrendReport(
            platform_reports=[report],
            top_insights=["AI Agent가 대세"],
        )
        text = merged.to_summary_text()
        assert "AI Agent" in text
        assert "X" in text.upper()

    def test_to_summary_text_with_sentiment(self):
        trend = PlatformTrend(
            keyword="LLM", volume=50,
            sentiment="positive", confidence=85,
            hook_starter="LLM이 바꾸는 미래",
        )
        report = PlatformTrendReport(platform="threads", trends=[trend])
        merged = MergedTrendReport(platform_reports=[report])
        text = merged.to_summary_text()
        assert "positive" in text
        assert "85%" in text
        assert "LLM이 바꾸는 미래" in text


# ─── UnifiedChecklist ─────────────────────────────


class TestUnifiedChecklist:
    def test_to_checklist_text(self):
        cl = UnifiedChecklist(
            do_items=[{"platform": "x", "action": "해시태그 2개 이하"}],
            dont_items=[{"platform": "naver", "action": "외부 링크 삽입", "severity": "높음"}],
        )
        text = cl.to_checklist_text()
        assert "해시태그" in text
        assert "외부 링크" in text
        assert "DO" in text
        assert "DON'T" in text


# ─── PlatformTrend defaults ──────────────────────


class TestPlatformTrend:
    def test_defaults(self):
        t = PlatformTrend(keyword="test")
        assert t.sentiment == "neutral"
        assert t.confidence == 0
        assert t.optimal_post_hour == -1
