"""Tests for database layer."""

import tempfile
from datetime import datetime, timedelta

from models import DMTriggerRule, InstagramPost, PostInsights, PostStatus, PostType
from services.database import Database


def _make_db():
    tmp = tempfile.mktemp(suffix=".db")
    return Database(tmp)


def test_enqueue_and_fetch():
    db = _make_db()
    post = InstagramPost(
        caption="Test",
        hashtags="#test",
        image_url="https://example.com/img.jpg",
        post_type=PostType.IMAGE,
        scheduled_at=datetime.now() - timedelta(minutes=1),
    )
    pid = db.enqueue_post(post)
    assert pid > 0

    queued = db.get_queued_posts()
    assert len(queued) == 1
    assert queued[0].caption == "Test"


def test_get_next_scheduled():
    db = _make_db()
    # Future post — should NOT be returned
    future = InstagramPost(
        caption="Future",
        scheduled_at=datetime.now() + timedelta(hours=2),
    )
    db.enqueue_post(future)
    assert db.get_next_scheduled() is None

    # Past post — should be returned
    past = InstagramPost(
        caption="Past",
        scheduled_at=datetime.now() - timedelta(minutes=5),
    )
    db.enqueue_post(past)
    result = db.get_next_scheduled()
    assert result is not None
    assert result.caption == "Past"


def test_update_status():
    db = _make_db()
    post = InstagramPost(
        caption="Publish me",
        scheduled_at=datetime.now() - timedelta(minutes=1),
    )
    pid = db.enqueue_post(post)

    db.update_post_status(pid, PostStatus.PUBLISHED, media_id="ig_12345")
    published = db.get_published_posts()
    assert len(published) == 1
    assert published[0].media_id == "ig_12345"


def test_dm_rules():
    db = _make_db()
    db.add_dm_rule(DMTriggerRule(keyword="price", response_template="$99"))
    db.add_dm_rule(DMTriggerRule(keyword="info", response_template="See bio"))

    rules = db.get_dm_rules()
    assert len(rules) == 2
    assert rules[0].keyword in ("price", "info")


def test_insights():
    db = _make_db()
    ins = PostInsights(media_id="m_123", reach=500, engagement=25)
    db.save_insights(ins)

    result = db.get_insights_for_post("m_123")
    assert len(result) == 1
    assert result[0].reach == 500
    assert result[0].engagement_rate == 5.0


def test_post_count_today():
    db = _make_db()
    post = InstagramPost(
        caption="Today",
        scheduled_at=datetime.now() - timedelta(minutes=1),
    )
    pid = db.enqueue_post(post)
    assert db.get_post_count_today() == 0

    db.update_post_status(pid, PostStatus.PUBLISHED)
    assert db.get_post_count_today() == 1


def test_dm_log():
    db = _make_db()
    db.log_dm("user_1", "hello", "hi there", "greeting")
    # Just verify it doesn't crash — no read API for dm_log yet
