"""Tests for Phase 2: Content Calendar, Hashtag Strategy, A/B Testing."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _tmp_db():
    return tempfile.mktemp(suffix=".db")


# ---- Content Calendar Tests ----


class TestContentCalendar:
    def test_generate_weekly_plan(self):
        from services.content_calendar import ContentCalendar

        cal = ContentCalendar(_tmp_db())
        entries = cal.generate_weekly_plan(posting_hours=[12])
        assert len(entries) == 7
        themes = {e.theme for e in entries}
        assert "education" in themes
        assert "engagement" in themes

    def test_generate_weekly_plan_multiple_hours(self):
        from services.content_calendar import ContentCalendar

        cal = ContentCalendar(_tmp_db())
        entries = cal.generate_weekly_plan(posting_hours=[9, 18])
        assert len(entries) == 14  # 7 days × 2 hours

    def test_no_duplicate_entries(self):
        from services.content_calendar import ContentCalendar

        db = _tmp_db()
        cal = ContentCalendar(db)
        first = cal.generate_weekly_plan(posting_hours=[12])
        second = cal.generate_weekly_plan(posting_hours=[12])
        assert len(first) == 7
        assert len(second) == 0  # all already exist

    def test_inject_trend(self):
        from services.content_calendar import ContentCalendar

        cal = ContentCalendar(_tmp_db())
        entries = cal.generate_weekly_plan(posting_hours=[12])
        date = entries[0].date
        result = cal.inject_trend_topic(date, "AI 혁명", posting_hour=12)
        assert result is True

    def test_today_plan(self):
        from services.content_calendar import ContentCalendar

        cal = ContentCalendar(_tmp_db())
        plan = cal.get_today_plan()
        assert isinstance(plan, list)

    def test_stats(self):
        from services.content_calendar import ContentCalendar

        cal = ContentCalendar(_tmp_db())
        cal.generate_weekly_plan(posting_hours=[12])
        stats = cal.get_stats()
        assert stats["total"] == 7
        assert stats["planned"] == 7
        assert stats["completed"] == 0

    def test_mark_completed(self):
        from services.content_calendar import ContentCalendar

        cal = ContentCalendar(_tmp_db())
        entries = cal.generate_weekly_plan(posting_hours=[12])
        date = entries[0].date
        cal.mark_completed(date, 12)
        stats = cal.get_stats()
        assert stats["completed"] == 1


# ---- Hashtag Strategy Tests ----


class TestHashtagDB:
    def test_seed_defaults(self):
        from services.hashtag_strategy import HashtagDB

        db = HashtagDB(_tmp_db())
        count = db.seed_defaults(["tech"])
        assert count > 0

    def test_add_and_ban(self):
        from services.hashtag_strategy import HashtagDB

        db = HashtagDB(_tmp_db())
        db.add_tag("#mytest", "general", "small")
        db.ban_tag("#mytest")
        stats = db.get_stats()
        assert stats["banned_tags"] >= 1

    def test_get_optimized_set(self):
        from services.hashtag_strategy import HashtagDB

        db = HashtagDB(_tmp_db())
        db.seed_defaults(["tech", "korean_general"])
        tags = db.get_optimized_set(niche="tech", count=10)
        assert len(tags) <= 10
        assert all(t.startswith("#") for t in tags)

    def test_record_performance(self):
        from services.hashtag_strategy import HashtagDB

        db = HashtagDB(_tmp_db())
        db.seed_defaults(["tech"])
        db.record_performance(["#technology", "#ai"], reach=1000, engagement=50)
        top = db.get_top_performers(niche="tech", limit=5)
        assert len(top) > 0

    def test_save_and_get_set(self):
        from services.hashtag_strategy import HashtagDB

        db = HashtagDB(_tmp_db())
        db.save_set("my_set", "tech", ["#a", "#b", "#c"])
        result = db.get_set("my_set")
        assert result == ["#a", "#b", "#c"]

    def test_get_set_missing(self):
        from services.hashtag_strategy import HashtagDB

        db = HashtagDB(_tmp_db())
        assert db.get_set("nonexistent") is None

    def test_stats(self):
        from services.hashtag_strategy import HashtagDB

        db = HashtagDB(_tmp_db())
        db.seed_defaults()
        stats = db.get_stats()
        assert stats["total_tags"] > 0
        assert "tech" in stats["by_niche"]


# ---- A/B Testing Tests ----


class TestABTestEngine:
    def test_create_caption_test(self):
        from services.ab_testing import ABTestEngine

        engine = ABTestEngine(_tmp_db())
        exp_id = engine.create_caption_test(
            topic="AI 트렌드",
            variant_a="AI가 바꾸는 세상",
            variant_b="당신이 모르는 AI의 비밀",
        )
        assert exp_id > 0

    def test_get_active_experiments(self):
        from services.ab_testing import ABTestEngine

        engine = ABTestEngine(_tmp_db())
        engine.create_caption_test("test", "A", "B")
        active = engine.get_active_experiments()
        assert len(active) == 1

    def test_record_and_results(self):
        from services.ab_testing import ABTestEngine

        engine = ABTestEngine(_tmp_db())
        exp_id = engine.create_caption_test("test", "A caption", "B caption")

        # Record results for variant A (id=1)
        engine.record_results(1, reach=1000, engagement=50, likes=30, saved=10)
        # Record results for variant B (id=2)
        engine.record_results(2, reach=1000, engagement=80, likes=60, saved=20)

        results = engine.get_experiment_results(exp_id)
        assert results["winner"] == "B"
        assert len(results["variants"]) == 2

    def test_significance_check(self):
        from services.ab_testing import ABTestEngine

        engine = ABTestEngine(_tmp_db())
        exp_id = engine.create_caption_test("sig_test", "A", "B")
        engine.record_results(1, reach=1000, engagement=50)
        engine.record_results(2, reach=1000, engagement=80)

        results = engine.get_experiment_results(exp_id)
        sig = results["significance"]
        assert sig is not None
        assert "z_score" in sig

    def test_complete_and_learnings(self):
        from services.ab_testing import ABTestEngine

        engine = ABTestEngine(_tmp_db())
        exp_id = engine.create_caption_test("learn", "A", "B")
        engine.record_results(1, reach=100, engagement=5)
        engine.record_results(2, reach=100, engagement=15)

        engine.complete_experiment(exp_id)
        learnings = engine.get_learnings()
        assert len(learnings) == 1
        assert learnings[0]["winner"] == "B"

    def test_hashtag_test(self):
        from services.ab_testing import ABTestEngine

        engine = ABTestEngine(_tmp_db())
        exp_id = engine.create_hashtag_test(
            "AI",
            ["#ai", "#tech"],
            ["#artificialintelligence", "#ml"],
        )
        assert exp_id > 0
        results = engine.get_experiment_results(exp_id)
        assert len(results["variants"]) == 2

    def test_missing_experiment(self):
        from services.ab_testing import ABTestEngine

        engine = ABTestEngine(_tmp_db())
        results = engine.get_experiment_results(999)
        assert "error" in results
