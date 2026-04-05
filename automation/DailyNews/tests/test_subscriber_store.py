"""Unit tests for SubscriberStore — CRUD, engagement scoring, and stats."""

from __future__ import annotations

from pathlib import Path

import pytest

from antigravity_mcp.integrations.subscriber_store import SubscriberStore


@pytest.fixture
def store(tmp_path: Path) -> SubscriberStore:
    """Create an in-memory-equivalent subscriber store via tmp dir."""
    db_path = tmp_path / "test_newsletter.db"
    return SubscriberStore(db_path=db_path)


class TestSubscriberCRUD:
    def test_add_subscriber(self, store: SubscriberStore) -> None:
        sub = store.add_subscriber("test@example.com", name="Alice", categories=["Economy_KR"])
        assert sub is not None
        assert sub.email == "test@example.com"
        assert sub.name == "Alice"
        assert sub.categories == ["Economy_KR"]
        assert sub.status == "active"
        assert sub.engagement_score == 0.0

    def test_add_duplicate_returns_none(self, store: SubscriberStore) -> None:
        store.add_subscriber("dup@example.com")
        result = store.add_subscriber("dup@example.com")
        assert result is None

    def test_add_normalizes_email(self, store: SubscriberStore) -> None:
        sub = store.add_subscriber("  UPPER@Example.COM  ")
        assert sub is not None
        assert sub.email == "upper@example.com"

    def test_get_subscriber_by_email(self, store: SubscriberStore) -> None:
        store.add_subscriber("lookup@example.com", name="Bob")
        found = store.get_subscriber_by_email("lookup@example.com")
        assert found is not None
        assert found.name == "Bob"

    def test_get_subscriber_not_found(self, store: SubscriberStore) -> None:
        assert store.get_subscriber_by_email("nonexistent@example.com") is None

    def test_get_subscriber_by_email_quarantines_corrupt_categories_json(
        self,
        store: SubscriberStore,
    ) -> None:
        store.add_subscriber("corrupt_lookup@test.com", categories=["Tech"])
        conn = store._connect()
        conn.execute(
            "UPDATE subscribers SET categories_json = ? WHERE email = ?",
            ("{not-json", "corrupt_lookup@test.com"),
        )
        conn.commit()

        found = store.get_subscriber_by_email("corrupt_lookup@test.com")
        assert found is not None
        assert found.categories == []

    def test_get_active_subscribers(self, store: SubscriberStore) -> None:
        store.add_subscriber("a@test.com", categories=["Tech"])
        store.add_subscriber("b@test.com", categories=["Economy_KR"])
        store.add_subscriber("c@test.com", categories=["Tech", "Economy_KR"])

        all_active = store.get_active_subscribers()
        assert len(all_active) == 3

        tech_only = store.get_active_subscribers(categories=["Tech"])
        emails = {s.email for s in tech_only}
        assert "a@test.com" in emails
        assert "c@test.com" in emails

    def test_get_active_subscribers_with_no_pref_gets_all(self, store: SubscriberStore) -> None:
        """Subscribers with empty categories should match any category filter."""
        store.add_subscriber("nopref@test.com", categories=[])
        store.add_subscriber("techonly@test.com", categories=["Tech"])

        result = store.get_active_subscribers(categories=["Economy_KR"])
        emails = {s.email for s in result}
        # nopref has no category constraint, so should also be included
        assert "nopref@test.com" in emails

    def test_get_active_subscribers_skips_corrupt_categories_json(
        self,
        store: SubscriberStore,
    ) -> None:
        store.add_subscriber("healthy@test.com", categories=["Tech"])
        store.add_subscriber("corrupt@test.com", categories=["Economy_KR"])
        conn = store._connect()
        conn.execute(
            "UPDATE subscribers SET categories_json = ? WHERE email = ?",
            ("{not-json", "corrupt@test.com"),
        )
        conn.commit()

        result = store.get_active_subscribers(categories=["Tech"])
        emails = {subscriber.email for subscriber in result}

        assert emails == {"healthy@test.com"}


class TestSubscriberStatusTransitions:
    def test_unsubscribe(self, store: SubscriberStore) -> None:
        store.add_subscriber("unsub@test.com")
        assert store.unsubscribe("unsub@test.com") is True

        found = store.get_subscriber_by_email("unsub@test.com")
        assert found is not None
        assert found.status == "unsubscribed"
        assert not found.is_active

    def test_unsubscribe_nonexistent(self, store: SubscriberStore) -> None:
        assert store.unsubscribe("nobody@test.com") is False

    def test_pause_and_reactivate(self, store: SubscriberStore) -> None:
        store.add_subscriber("pauseme@test.com")
        store.pause("pauseme@test.com")

        found = store.get_subscriber_by_email("pauseme@test.com")
        assert found is not None
        assert found.status == "paused"

        store.reactivate("pauseme@test.com")
        found = store.get_subscriber_by_email("pauseme@test.com")
        assert found is not None
        assert found.status == "active"

    def test_paused_excluded_from_active(self, store: SubscriberStore) -> None:
        store.add_subscriber("active@test.com")
        store.add_subscriber("paused@test.com")
        store.pause("paused@test.com")

        active = store.get_active_subscribers()
        emails = {s.email for s in active}
        assert "active@test.com" in emails
        assert "paused@test.com" not in emails


class TestEngagementScoring:
    def test_initial_score_is_zero(self, store: SubscriberStore) -> None:
        sub = store.add_subscriber("score@test.com")
        assert sub is not None
        assert sub.engagement_score == 0.0

    def test_opened_increases_score(self, store: SubscriberStore) -> None:
        sub = store.add_subscriber("opener@test.com")
        assert sub is not None
        store.update_engagement_score(sub.id, opened=True)

        found = store.get_subscriber_by_email("opener@test.com")
        assert found is not None
        # 0.7 * 0.0 + 0.3 * 0.5 = 0.15
        assert found.engagement_score == pytest.approx(0.15, abs=0.01)

    def test_clicked_increases_score_more(self, store: SubscriberStore) -> None:
        sub = store.add_subscriber("clicker@test.com")
        assert sub is not None
        store.update_engagement_score(sub.id, clicked=True)

        found = store.get_subscriber_by_email("clicker@test.com")
        assert found is not None
        # 0.7 * 0.0 + 0.3 * 1.0 = 0.30
        assert found.engagement_score == pytest.approx(0.30, abs=0.01)

    def test_ema_accumulates(self, store: SubscriberStore) -> None:
        """Test that Exponential Moving Average accumulates correctly."""
        sub = store.add_subscriber("ema@test.com")
        assert sub is not None

        # Round 1: opened → score = 0.15
        store.update_engagement_score(sub.id, opened=True)
        # Round 2: clicked → score = 0.7 * 0.15 + 0.3 * 1.0 = 0.105 + 0.3 = 0.405
        store.update_engagement_score(sub.id, clicked=True)

        found = store.get_subscriber_by_email("ema@test.com")
        assert found is not None
        assert found.engagement_score == pytest.approx(0.405, abs=0.01)


class TestEvents:
    def test_record_event(self, store: SubscriberStore) -> None:
        sub = store.add_subscriber("events@test.com")
        assert sub is not None
        store.record_event(sub.id, "delivered", "report_001")
        store.record_event(sub.id, "opened", "report_001")
        # No assertion on return, just ensure no crash

    def test_record_event_with_metadata(self, store: SubscriberStore) -> None:
        sub = store.add_subscriber("meta@test.com")
        assert sub is not None
        store.record_event(sub.id, "clicked", "report_002", metadata={"link": "https://example.com"})


class TestStats:
    def test_get_stats_empty(self, store: SubscriberStore) -> None:
        stats = store.get_stats()
        assert stats["total"] == 0
        assert stats["active"] == 0
        assert stats["avg_engagement"] == 0.0
        assert stats["category_distribution"] == {}

    def test_get_stats_with_data(self, store: SubscriberStore) -> None:
        store.add_subscriber("a@test.com", categories=["Tech", "AI_Deep"])
        store.add_subscriber("b@test.com", categories=["Economy_KR"])
        store.add_subscriber("c@test.com", categories=["Tech"])

        stats = store.get_stats()
        assert stats["total"] == 3
        assert stats["active"] == 3
        assert stats["category_distribution"]["Tech"] == 2
        assert stats["category_distribution"]["Economy_KR"] == 1
        assert stats["category_distribution"]["AI_Deep"] == 1

    def test_get_stats_skips_corrupt_categories_json(self, store: SubscriberStore) -> None:
        store.add_subscriber("healthy@test.com", categories=["Tech"])
        store.add_subscriber("corrupt@test.com", categories=["Economy_KR"])
        conn = store._connect()
        conn.execute(
            "UPDATE subscribers SET categories_json = ? WHERE email = ?",
            ("{not-json", "corrupt@test.com"),
        )
        conn.commit()

        stats = store.get_stats()

        assert stats["total"] == 2
        assert stats["active"] == 2
        assert stats["category_distribution"]["Tech"] == 1
        assert "Economy_KR" not in stats["category_distribution"]

    def test_get_subscriber_count(self, store: SubscriberStore) -> None:
        store.add_subscriber("count1@test.com")
        store.add_subscriber("count2@test.com")
        store.add_subscriber("count3@test.com")
        store.unsubscribe("count3@test.com")

        assert store.get_subscriber_count() == 2


class TestCategoryUpdate:
    def test_update_categories(self, store: SubscriberStore) -> None:
        store.add_subscriber("cats@test.com", categories=["Tech"])
        assert store.update_categories("cats@test.com", ["Economy_KR", "AI_Deep"]) is True

        found = store.get_subscriber_by_email("cats@test.com")
        assert found is not None
        assert set(found.categories) == {"Economy_KR", "AI_Deep"}

    def test_update_categories_nonexistent(self, store: SubscriberStore) -> None:
        assert store.update_categories("nobody@test.com", ["Tech"]) is False
