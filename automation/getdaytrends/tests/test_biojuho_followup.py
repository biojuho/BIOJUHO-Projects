import unittest

from config import AppConfig
from content_qa import _audit_content_group
from generation.long_form import _system_blog_post
from models import GeneratedTweet, MultiSourceContext, ScoredTrend
from prompt_builder import _system_threads, _system_tweets, _use_report_profile


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
