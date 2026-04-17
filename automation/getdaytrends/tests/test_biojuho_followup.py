import unittest

from config import AppConfig
from content_qa import _audit_content_group
from generation.long_form import _system_blog_post
from models import GeneratedTweet, MultiSourceContext, ScoredTrend
from prompt_builder import (
    _BLOG_STRUCTURE_POOL,
    _build_ai_frame_guard_section,
    _build_blog_structure_section,
    _system_threads,
    _system_tweets,
    _trend_is_ai_native,
    _use_report_profile,
)


def _make_trend(keyword: str = "Systems memo", top_insight: str = "workflow governance") -> ScoredTrend:
    return ScoredTrend(
        keyword=keyword,
        rank=1,
        viral_potential=86,
        category="tech",
        top_insight=top_insight,
        context=MultiSourceContext(
            twitter_insight="operator thread describing workflow bottlenecks in detail",
            news_insight="case study coverage with concrete implementation evidence",
        ),
    )


class TestBiojuhoPromptRouting(unittest.TestCase):
    def test_biojuho_tweets_prompt_uses_lens_rotation(self):
        prompt = _system_tweets("biojuho")
        self.assertIn("historical_parallel", prompt)
        self.assertIn("counter_thesis", prompt)

    def test_biojuho_threads_prompt_is_not_report_brief(self):
        prompt = _system_threads("biojuho", "biojuho")
        self.assertIn("not a news brief", prompt)
        self.assertIn("no hashtags", prompt)

    def test_biojuho_blog_prompt_avoids_fixed_report_template(self):
        prompt = _system_blog_post("biojuho", "biojuho")
        self.assertIn("do not use a fixed four-heading report template", prompt)

    def test_report_profile_is_disabled_for_biojuho_tone(self):
        cfg = AppConfig()
        cfg.tone = "biojuho"
        cfg.editorial_profile = "report"
        self.assertFalse(_use_report_profile(cfg))


class TestBiojuhoQAGuards(unittest.TestCase):
    def test_ai_frame_overuse_is_flagged_for_non_ai_topic(self):
        trend = _make_trend(keyword="Spring haircut", top_insight="shape and fit matter more than trend labels")
        config = AppConfig()
        config.tone = "biojuho"
        result = _audit_content_group(
            "tweets",
            [
                GeneratedTweet(
                    tweet_type="observation",
                    content=(
                        "AI picks the haircut. AI sets the standard. "
                        "AI becomes the answer. AI remains and the face shape disappears."
                    ),
                )
            ],
            trend,
            config,
        )

        self.assertTrue(any("AI framing overuse" in issue for issue in result["issues"]))

    def test_repeated_clipped_endings_are_flagged(self):
        trend = _make_trend()
        config = AppConfig()
        config.tone = "biojuho"
        result = _audit_content_group(
            "tweets",
            [
                GeneratedTweet(
                    tweet_type="observation",
                    content=(
                        "\uC774\uAC74 \uAD6C\uC870 \uBB38\uC81C\uC784. "
                        "\uB370\uC774\uD130\uB3C4 \uC5C6\uC74C. "
                        "\uD574\uC11D\uB3C4 \uACF5\uD5C8\uD568\uC784. "
                        "\uADF8\uB798\uC11C \uBB34\uAC8C\uB3C4 \uC5C6\uC74C."
                    ),
                )
            ],
            trend,
            config,
        )

        self.assertTrue(any("repeated clipped endings" in issue for issue in result["issues"]))


class TestBiojuhoBlogStructurePool(unittest.TestCase):
    def test_pool_contains_six_distinct_patterns(self):
        labels = [label for label, _ in _BLOG_STRUCTURE_POOL]
        self.assertEqual(len(labels), 6)
        self.assertEqual(len(set(labels)), 6)
        self.assertEqual(
            set(labels),
            {"pattern_a", "pattern_b", "pattern_c", "pattern_d", "pattern_e", "pattern_f"},
        )

    def test_pool_includes_new_structures_from_followup(self):
        combined = "\n".join(description for _, description in _BLOG_STRUCTURE_POOL)
        self.assertIn("signal", combined)
        self.assertIn("misread", combined)
        self.assertIn("anecdote", combined)
        self.assertIn("contradiction", combined)
        self.assertIn("timeline", combined)
        self.assertIn("inflection", combined)

    def test_structure_section_is_deterministic_for_keyword(self):
        trend = _make_trend(keyword="Fed pivot")
        first = _build_blog_structure_section(trend)
        second = _build_blog_structure_section(trend)
        self.assertEqual(first, second)

    def test_structure_section_varies_across_keywords(self):
        labels: set[str] = set()
        for keyword in (
            "Fed pivot",
            "AI cluster outage",
            "Korean biotech licensing",
            "Samsung foundry leak",
            "Seoul housing inflection",
            "World Cup broadcast rights",
            "K-pop label consolidation",
            "Defense export deal",
        ):
            section = _build_blog_structure_section(_make_trend(keyword=keyword))
            for label, _ in _BLOG_STRUCTURE_POOL:
                if f"Selected layout: {label}" in section:
                    labels.add(label)
                    break
        self.assertGreaterEqual(len(labels), 3)


class TestAIConvergenceGuardV2(unittest.TestCase):
    def test_guard_is_empty_for_ai_native_topic(self):
        trend = _make_trend(
            keyword="GPT-5 release rumor",
            top_insight="OpenAI model rollout timeline",
        )
        self.assertTrue(_trend_is_ai_native(trend))
        self.assertEqual(_build_ai_frame_guard_section(trend), "")

    def test_guard_activates_for_non_ai_topic(self):
        trend = _make_trend(
            keyword="Spring haircut",
            top_insight="shape and fit over trend labels",
        )
        trend.context = MultiSourceContext(
            twitter_insight="stylists discussing seasonal shape changes",
            news_insight="lifestyle magazine coverage of spring styling",
        )
        self.assertFalse(_trend_is_ai_native(trend))
        section = _build_ai_frame_guard_section(trend)
        self.assertIn("[AI Frame Guard]", section)
        self.assertIn("At most 1 of the 5 drafts", section)
        self.assertIn("At least 1 draft must avoid", section)

    def test_guard_detects_korean_ai_native_signal(self):
        trend = _make_trend(
            keyword="국내 인공지능 규제",
            top_insight="생성형 모델 관련 가이드라인 논의",
        )
        self.assertTrue(_trend_is_ai_native(trend))
        self.assertEqual(_build_ai_frame_guard_section(trend), "")

    def test_guard_detects_agent_keyword_as_ai_native(self):
        trend = _make_trend(
            keyword="Multi-agent orchestration breakdown",
            top_insight="agent coordination failure modes",
        )
        self.assertTrue(_trend_is_ai_native(trend))

    def test_guard_ignores_empty_trend_fields(self):
        trend = ScoredTrend(
            keyword="",
            rank=1,
            viral_potential=60,
            category="",
            top_insight="",
        )
        self.assertFalse(_trend_is_ai_native(trend))
        self.assertIn("[AI Frame Guard]", _build_ai_frame_guard_section(trend))
