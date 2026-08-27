"""Tests for the local creator reference library."""

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from live_reference_collector import YouTubeLiveReferenceCollector  # noqa: E402
from reference_library import (  # noqa: E402
    DuplicateReferenceError,
    ReferenceItemCreate,
    ReferenceItemPatch,
    ReferenceLibraryStore,
    canonicalize_source_url,
)


def _reference(**overrides) -> ReferenceItemCreate:
    payload = {
        "title": "레퍼런스 콘텐츠",
        "source_url": "https://youtu.be/example?si=tracking&utm_source=test",
        "platform": "youtube",
        "keyword": "콘텐츠 발굴",
        "content_format": "short",
        "recommendation_score": 88,
        "summary": "키워드 기반 레퍼런스 수집과 추천 점수 활용",
    }
    payload.update(overrides)
    return ReferenceItemCreate(**payload)


def test_canonicalize_source_url_removes_tracking_parameters():
    assert canonicalize_source_url("https://YOUTU.BE/example/?si=abc&utm_campaign=launch&t=15#clip") == (
        "https://youtu.be/example?t=15"
    )


def test_store_create_filter_update_and_persist(tmp_path):
    store_path = tmp_path / "reference_library.json"
    store = ReferenceLibraryStore(store_path)
    first = store.create(_reference())
    store.create(
        _reference(
            title="Threads 아이디어",
            source_url="https://www.threads.net/@creator/post/123",
            platform="threads",
            content_format="thread",
            recommendation_score=64,
        )
    )

    assert [item["id"] for item in store.list()] == [first["id"], store.list()[1]["id"]]
    assert [item["title"] for item in store.list(query="키워드", platform="youtube", min_score=80)] == [
        "레퍼런스 콘텐츠"
    ]

    updated = store.update(first["id"], ReferenceItemPatch(saved=True, read=True, memo="후킹 구조 적용"))
    assert updated["saved"] is True
    assert updated["read"] is True
    assert updated["memo"] == "후킹 구조 적용"
    assert store.stats() == {
        "total": 2,
        "saved": 1,
        "unread": 1,
        "recommended": 1,
        "by_platform": {"threads": 1, "youtube": 1},
    }

    reopened = ReferenceLibraryStore(store_path)
    assert reopened.get(first["id"])["memo"] == "후킹 구조 적용"


def test_store_rejects_duplicate_canonical_url(tmp_path):
    store = ReferenceLibraryStore(tmp_path / "reference_library.json")
    store.create(_reference(source_url="https://youtu.be/example?si=first"))

    with pytest.raises(DuplicateReferenceError):
        store.create(_reference(source_url="https://youtu.be/example?si=second"))


@pytest.mark.asyncio
async def test_live_collector_separates_live_queue_and_populates_detailed_metadata(tmp_path):
    store = ReferenceLibraryStore(tmp_path / "live-library.json")
    collector = YouTubeLiveReferenceCollector(store, executable="/fake/yt-dlp")
    collector._search_keyword = AsyncMock(
        return_value=[
            {
                "id": "live123",
                "title": "지금 뜨는 AI 콘텐츠 제작법",
                "url": "https://www.youtube.com/watch?v=live123",
                "channel": "라이브 채널",
                "duration": 58,
                "view_count": 120_000,
                "like_count": 4_500,
                "comment_count": 320,
                "timestamp": 1787666400,
                "description": "AI 콘텐츠 제작과 유튜브 성장 팁을 공유합니다.",
            }
        ]
    )

    first = await collector.refresh(["AI 콘텐츠"], per_keyword=3)
    assert first["collected"] == 1
    assert first["new_count"] == 1
    assert first["repeat_count"] == 0
    assert first["created"] == 0
    assert first["updated"] == 0
    assert first["errors"] == []
    assert first["is_stale"] is False
    assert first["last_success_at"] is not None

    # Permanent library items are NOT polluted by auto live search
    assert len(store.list()) == 0
    assert len(store.get_live_items()) == 1

    item = first["items"][0]
    assert item["id"] == "live123"
    assert item["platform"] == "youtube"
    assert item["content_format"] == "short"
    assert item["published_at"] != ""
    assert item["age_hours"] is not None
    assert item["age_text"] != ""
    assert item["views"] == 120_000
    assert item["views_per_hour"] is not None
    assert item["likes"] == 4_500
    assert item["comments"] == 320
    assert item["duration"] == 58
    assert item["duration_formatted"] == "0:58"
    assert item["topic_relevance"] >= 70
    assert item["recommendation_score"] >= 80
    assert "급상승" in item["recommendation_reason"] or "반응" in item["recommendation_reason"] or "AI 콘텐츠" in item["recommendation_reason"]
    assert item["is_new"] is True
    assert item["status"] == "new"

    # Second refresh with same item: detected as repeat
    second = await collector.refresh(["AI 콘텐츠"], per_keyword=3)
    assert second["collected"] == 1
    assert second["new_count"] == 0
    assert second["repeat_count"] == 1
    assert second["created"] == 0
    assert second["updated"] == 0
    assert second["items"][0]["is_new"] is False
    assert second["items"][0]["status"] == "repeat"
    assert len(store.list()) == 0


@pytest.mark.asyncio
async def test_live_collector_keyword_failure_isolation(tmp_path):
    store = ReferenceLibraryStore(tmp_path / "live-library.json")
    collector = YouTubeLiveReferenceCollector(store, executable="/fake/yt-dlp")

    async def mock_search(keyword: str, limit: int):
        if keyword == "실패키워드":
            raise RuntimeError("Network connection reset by peer")
        return [
            {
                "id": "good456",
                "title": "성공한 유튜브 성장 전략",
                "url": "https://www.youtube.com/watch?v=good456",
                "channel": "성장 채널",
                "duration": 600,
                "view_count": 50_000,
                "timestamp": 1787666400,
            }
        ]

    collector._search_keyword = AsyncMock(side_effect=mock_search)

    status = await collector.refresh(["실패키워드", "유튜브 성장"], per_keyword=3)
    assert status["available"] is True
    assert status["collected"] == 1
    assert len(status["items"]) == 1
    assert status["items"][0]["id"] == "good456"
    assert len(status["errors"]) == 1
    assert "실패키워드" in status["errors"][0]
    assert status["last_success_at"] is not None


@pytest.mark.asyncio
async def test_live_collector_transient_full_failure_preserves_last_good_items(tmp_path):
    store = ReferenceLibraryStore(tmp_path / "live-library.json")
    collector = YouTubeLiveReferenceCollector(store, executable="/fake/yt-dlp")

    collector._search_keyword = AsyncMock(
        return_value=[
            {
                "id": "item1",
                "title": "정상 수집 AI 콘텐츠",
                "url": "https://www.youtube.com/watch?v=item1",
                "channel": "정상 채널",
                "duration": 300,
                "view_count": 10_000,
                "timestamp": 1787666400,
            }
        ]
    )

    first = await collector.refresh(["AI 콘텐츠"], per_keyword=3)
    assert first["collected"] == 1
    assert first["is_stale"] is False
    last_success = first["last_success_at"]
    assert last_success is not None

    # Now simulate a transient full failure (e.g. yt-dlp error on all keywords)
    collector._search_keyword = AsyncMock(side_effect=RuntimeError("YouTube 429 Too Many Requests"))
    second = await collector.refresh(["AI 콘텐츠"], per_keyword=3)

    assert second["collected"] == 1
    assert len(second["items"]) == 1
    assert second["items"][0]["id"] == "item1"
    assert second["last_success_at"] == last_success
    assert second["is_stale"] is True
    assert len(second["errors"]) > 0


@pytest.mark.asyncio
async def test_live_collector_filters_spam_and_excluded_topics(tmp_path):
    store = ReferenceLibraryStore(tmp_path / "live-library.json")
    collector = YouTubeLiveReferenceCollector(store, executable="/fake/yt-dlp")

    collector._search_keyword = AsyncMock(
        return_value=[
            {
                "id": "spam1",
                "title": "사설토토 바카라 불법 홍보 영상",
                "url": "https://www.youtube.com/watch?v=spam1",
                "channel": "스팸채널",
                "duration": 60,
                "view_count": 999_999,
            },
            {
                "id": "clean1",
                "title": "AI 콘텐츠 기획 완벽 가이드",
                "url": "https://www.youtube.com/watch?v=clean1",
                "channel": "정상채널",
                "duration": 120,
                "view_count": 5_000,
                "timestamp": 1787666400,
            },
        ]
    )

    status = await collector.refresh(["AI 콘텐츠"], per_keyword=3)
    assert status["collected"] == 1
    assert [item["id"] for item in status["items"]] == ["clean1"]


@pytest.mark.asyncio
async def test_live_collector_enrichment_subprocess_fallback(tmp_path):
    store = ReferenceLibraryStore(tmp_path / "live-library.json")
    collector = YouTubeLiveReferenceCollector(store, executable="/fake/yt-dlp")

    collector._search_keyword = AsyncMock(
        return_value=[
            {
                "id": "flat123",
                "title": "AI 영상 제작 팁",
                "url": "https://www.youtube.com/watch?v=flat123",
                "channel": "채널",
                "duration": 150,
                "view_count": 30_000,
            }
        ]
    )
    # Mock detailed metadata fetch subprocess
    collector._fetch_detailed_metadata = AsyncMock(
        return_value={
            "id": "flat123",
            "timestamp": 1787666400,
            "upload_date": "20260825",
            "like_count": 1200,
            "comment_count": 85,
            "tags": ["AI", "영상제작"],
            "description": "AI 영상 제작 팁 상세 설명",
        }
    )

    status = await collector.refresh(["AI 영상"], per_keyword=3)
    assert status["collected"] == 1
    item = status["items"][0]
    assert item["likes"] == 1200
    assert item["comments"] == 85
    assert item["published_at"] != ""
    assert item["topic_relevance"] >= 70


@pytest.mark.asyncio
async def test_live_collector_strictly_excludes_videos_older_than_14_days(tmp_path):
    store = ReferenceLibraryStore(tmp_path / "live-library.json")
    collector = YouTubeLiveReferenceCollector(store, executable="/fake/yt-dlp", recent_days=14)

    collector._search_keyword = AsyncMock(
        return_value=[
            {
                "id": "old_2023",
                "title": "오래된 유튜브 성장 팁 2023",
                "url": "https://www.youtube.com/watch?v=old_2023",
                "channel": "옛날채널",
                "duration": 600,
                "view_count": 800_000,
                "upload_date": "20231029",  # 2023-10-29 (> 24,000 hours old)
            },
            {
                "id": "fresh_2026",
                "title": "2026 최신 유튜브 성장 전략",
                "url": "https://www.youtube.com/watch?v=fresh_2026",
                "channel": "최신채널",
                "duration": 480,
                "view_count": 25_000,
                "timestamp": int(datetime.now(UTC).timestamp()) - 86400,  # 1 day ago (24 hours)
            },
        ]
    )

    status = await collector.refresh(["유튜브 성장"], per_keyword=5)
    assert status["recent_days"] == 14
    assert status["max_age_hours"] == 336
    assert status["excluded_old_count"] == 1
    assert status["collected"] == 1
    assert len(status["items"]) == 1
    assert status["items"][0]["id"] == "fresh_2026"
    assert status["items"][0]["recency_verified"] is True
    assert status["items"][0]["age_hours"] <= 336.0


@pytest.mark.asyncio
async def test_live_collector_rejects_loose_search_topics_and_honors_output_limit(tmp_path):
    store = ReferenceLibraryStore(tmp_path / "live-library.json")
    collector = YouTubeLiveReferenceCollector(store, executable="/fake/yt-dlp")
    now = int(datetime.now(UTC).timestamp())
    collector._search_keyword = AsyncMock(
        return_value=[
            {
                "id": "cloud_growth",
                "title": "네오클라우드의 기묘한 성장법",
                "url": "https://www.youtube.com/watch?v=cloud_growth",
                "timestamp": now - 3600,
                "view_count": 500_000,
            },
            {
                "id": "work_life",
                "title": "사회생활 시작하면 알아야 할 것들",
                "url": "https://www.youtube.com/watch?v=work_life",
                "timestamp": now - 7200,
                "view_count": 400_000,
            },
            {
                "id": "youtube_growth_low",
                "title": "유튜브 채널 성장 기록",
                "url": "https://www.youtube.com/watch?v=youtube_growth_low",
                "timestamp": now - 3600,
                "view_count": 500,
            },
            {
                "id": "youtube_growth_high",
                "title": "구독자 늘리는 유튜브 성장 전략",
                "url": "https://www.youtube.com/watch?v=youtube_growth_high",
                "timestamp": now - 3600,
                "view_count": 50_000,
            },
        ]
    )

    status = await collector.refresh(["유튜브 성장"], per_keyword=1)

    assert status["collected"] == 1
    assert status["excluded_irrelevant_count"] == 2
    assert status["items"][0]["id"] == "youtube_growth_high"
    assert status["items"][0]["topic_relevance"] >= 85


@pytest.mark.asyncio
async def test_live_collector_handles_unverified_recency_and_caps_score(tmp_path):
    store = ReferenceLibraryStore(tmp_path / "live-library.json")
    collector = YouTubeLiveReferenceCollector(store, executable="/fake/yt-dlp")

    collector._search_keyword = AsyncMock(
        return_value=[
            {
                "id": "unverified_date",
                "title": "게시시각을 알 수 없는 AI 콘텐츠 영상",
                "url": "https://www.youtube.com/watch?v=unverified_date",
                "channel": "미확인채널",
                "duration": 50,
                "view_count": 500_000,
                # No timestamp or upload_date
            }
        ]
    )

    status = await collector.refresh(["AI 콘텐츠"], per_keyword=3)
    assert status["collected"] == 1
    item = status["items"][0]
    assert item["recency_verified"] is False
    assert item["age_hours"] is None
    assert item["age_text"] == "게시시각 미확인"
    assert item["views_per_hour"] is None
    # High score prevention (고점 방지): score capped at 45
    assert item["recommendation_score"] <= 45
    assert "게시시각 미확인" in item["recommendation_reason"]


@pytest.mark.asyncio
async def test_live_collector_search_query_includes_after_date_and_timeout_cleanup(tmp_path):
    store = ReferenceLibraryStore(tmp_path / "live-library.json")
    collector = YouTubeLiveReferenceCollector(store, executable="/fake/yt-dlp", recent_days=14)

    # Test subprocess execution wrapper with timeout cleanup
    with patch.object(collector, "_safe_run_subprocess", AsyncMock(side_effect=TimeoutError())):
        with pytest.raises(RuntimeError) as exc_info:
            await collector._search_keyword("AI 콘텐츠", limit=3, recent_days=14)
        assert "timed out" in str(exc_info.value)


@pytest.fixture
def client(tmp_path):
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi not installed")

    import dashboard
    import dashboard_routes_reference

    previous_store = dashboard_routes_reference._store
    previous_collector = dashboard_routes_reference._collector
    store = ReferenceLibraryStore(tmp_path / "api-library.json")
    collector = YouTubeLiveReferenceCollector(store, executable="/fake/yt-dlp")
    collector.refresh = AsyncMock(
        return_value={
            "available": True,
            "source": "youtube",
            "keywords": ["AI 콘텐츠"],
            "collected": 3,
            "created": 3,
            "updated": 0,
            "errors": [],
            "refreshed_at": "2026-08-05T00:00:00+00:00",
            "capabilities": collector.capabilities(),
        }
    )
    dashboard_routes_reference.init_reference_router(store, collector)
    try:
        with TestClient(dashboard.app) as test_client:
            yield test_client
    finally:
        dashboard_routes_reference._store = previous_store
        dashboard_routes_reference._collector = previous_collector


def test_dashboard_exposes_reference_library_ui(client):
    response = client.get("/")

    assert response.status_code == 200
    assert 'id="reference-library-title"' in response.text
    assert "LIVE 크리에이터 레퍼런스 레이더" in response.text
    assert "/api/reference-library" in response.text
    assert "X 속보·바이럴 원문 레이더" in response.text
    assert "/api/x-radar/refresh" in response.text
    assert "자동 문안 생성이나 게시 기능은 없습니다" in response.text
    assert "공개 X 상위 5위 반복" in response.text
    # 수동 버튼만 강제 수집 — 캐시 우회는 항상 켜져 있다.
    assert "force_refresh: true" in response.text
    assert "Threads 검색" in response.text
    assert "커뮤니티 바이럴 조기감지" in response.text
    assert "/api/fast-viral/refresh" in response.text
    assert "community_cluster_count" in response.text
    assert "cross_community_labels" in response.text


def test_dashboard_auto_polling_is_get_only_and_queue_is_separate(client):
    page = client.get("/").text

    # 자동 경로(첫 로드·setInterval)는 세 레인 전부 GET 스냅샷만 읽는다.
    assert "async function loadXRadar" in page
    assert "async function loadFastViral" in page
    assert "async function loadLiveReferences" in page
    assert "await fetch('/api/x-radar')" in page
    assert "await fetch('/api/fast-viral')" in page
    assert "await fetch('/api/reference-library/live/status')" in page
    assert "setInterval(() => loadXRadar(), 120000)" in page
    assert "setInterval(() => loadFastViral(), 120000)" in page
    assert "setInterval(() => loadLiveReferences(), 300000)" in page
    # 옛 자동 POST 경로는 사라졌다.
    assert "refreshXRadar(true)" not in page
    assert "refreshFastViral(true)" not in page
    assert "refreshLiveReferences(true)" not in page

    # YouTube 현재 큐는 영구 라이브러리 위 별도 섹션에 그린다.
    assert 'id="reference-live-queue"' in page
    assert "renderLiveReferences" in page
    # 썸네일 바이트는 받지 않는다 — 렌더가 유튜브 썸네일 URL을 쓰지 않는다.
    assert "i.ytimg.com" not in page
    assert "img.youtube.com" not in page
    assert "item.thumbnail" not in page

    # 커뮤니티 조기감지 레인은 국내 전용. 별도 사건 영상 큐의 Mastodon·PeerTube
    # 설명은 그대로 둘 수 있지만, 조기감지의 옛 해외 수집 문구는 없어야 한다.
    assert "국내 전용 · 해외 커뮤니티 수집 안 함" in page
    assert "국내 직접 원문과 Mastodon·Bluesky·Lemmy" not in page
    assert "글로벌 공개 ${safeHtml(String(data.federated_source_count" not in page


def test_dashboard_x_radar_ui_shows_four_separate_lanes(client):
    page = client.get("/").text

    # 응답의 분리 배열 4개가 각각의 섹션으로 렌더링된다.
    assert "breaking_now_items" in page
    assert "latest_news_items" in page
    assert "today_issue_items" in page
    assert "x_native_items" in page
    assert "지금 속보" in page
    assert "최신 뉴스" in page
    assert "오늘 이슈" in page
    assert "X 네이티브" in page
    assert "xRadarSectionHtml" in page
    # news_items가 비어 있는 기상청·연합뉴스 항목도 직접 원문을 잃지 않는다.
    assert "directSourceLink" in page
    assert "item.source_url" in page
    # freshness의 시계도 마지막 시도가 아니라 마지막 성공을 우선한다.
    assert "data.last_success_at || data.refreshed_at" in page


def test_fast_viral_refresh_endpoint(client):
    import dashboard_routes_fast_viral

    previous_collector = dashboard_routes_fast_viral._collector
    collector = SimpleNamespace(
        refresh=AsyncMock(
            return_value={
                "available": True,
                "items": [{"title": "조기 후보", "source_url": "https://www.fmkorea.com/123"}],
                "before_issuelink_count": 1,
                "source_health": {"fmkorea_direct": True, "issuelink_confirmation": True},
                "errors": [],
            }
        ),
        snapshot=lambda: {"available": False, "items": []},
    )
    dashboard_routes_fast_viral.init_fast_viral_router(collector)
    try:
        response = client.post("/api/fast-viral/refresh?limit=8")
    finally:
        dashboard_routes_fast_viral._collector = previous_collector

    assert response.status_code == 200
    assert response.json()["items"][0]["title"] == "조기 후보"
    collector.refresh.assert_awaited_once_with(limit=8)


def test_x_radar_refresh_endpoint(client):
    import dashboard_routes_x_radar

    previous_radar = dashboard_routes_x_radar._radar
    radar = SimpleNamespace(
        refresh=AsyncMock(
            return_value={
                "available": True,
                "items": [{"keyword": "속보", "news_items": [{"url": "https://news.example.com/live"}]}],
                "refreshed_at": "2026-08-05T00:00:00+00:00",
                "source_health": {"google_trends": True, "public_x_trends": True},
                "errors": [],
            }
        ),
        snapshot=lambda: {"available": False, "items": []},
    )
    dashboard_routes_x_radar.init_x_radar_router(radar)
    try:
        response = client.post(
            "/api/x-radar/refresh",
            json={"country": "korea", "limit": 10, "focus_keywords": ["AI"], "force_refresh": True},
        )
    finally:
        dashboard_routes_x_radar._radar = previous_radar

    assert response.status_code == 200
    assert response.json()["items"][0]["news_items"][0]["url"] == "https://news.example.com/live"
    radar.refresh.assert_awaited_once_with(
        country="korea", limit=10, focus_keywords=["AI"], force_refresh=True
    )


def test_reference_library_live_refresh_endpoint(client):
    response = client.post(
        "/api/reference-library/live/refresh",
        json={"keywords": ["AI 콘텐츠"], "per_keyword": 3},
    )

    assert response.status_code == 200
    assert response.json()["collected"] == 3
    status_response = client.get("/api/reference-library/live/status")
    assert status_response.status_code == 200
    assert status_response.json()["capabilities"]["youtube"]["available"] is True


def test_reference_library_api_round_trip(client):
    created = client.post(
        "/api/reference-library",
        json={
            "title": "상위 크리에이터 콘텐츠 발굴법",
            "source_url": "https://youtu.be/TtS525AJIIA?si=tracking",
            "platform": "youtube",
            "keyword": "레퍼런스 발굴",
            "content_format": "short",
            "recommendation_score": 92,
            "summary": "다중 플랫폼 콘텐츠를 한곳에서 수집하고 추천 점수로 우선순위를 정한다.",
        },
    )
    assert created.status_code == 201
    item = created.json()
    assert item["source_url"] == "https://youtu.be/TtS525AJIIA"

    duplicate = client.post(
        "/api/reference-library",
        json={
            "title": "중복",
            "source_url": "https://youtu.be/TtS525AJIIA?utm_source=duplicate",
            "platform": "youtube",
        },
    )
    assert duplicate.status_code == 409

    listed = client.get("/api/reference-library?platform=youtube&min_score=80&q=발굴")
    assert listed.status_code == 200
    assert [entry["id"] for entry in listed.json()["items"]] == [item["id"]]

    patched = client.patch(
        f"/api/reference-library/{item['id']}",
        json={"saved": True, "read": True, "memo": "우리 채널 키워드 세트로 확장"},
    )
    assert patched.status_code == 200
    assert patched.json()["memo"] == "우리 채널 키워드 세트로 확장"

    stats = client.get("/api/reference-library/stats")
    assert stats.status_code == 200
    assert stats.json()["saved"] == 1
    assert stats.json()["unread"] == 0


@pytest.mark.parametrize("source_url", ["file:///tmp/private", "https://user:secret@example.com/private"])
def test_reference_library_api_rejects_unsafe_url(client, source_url):
    response = client.post(
        "/api/reference-library",
        json={"title": "안전하지 않은 URL", "source_url": source_url, "platform": "other"},
    )

    assert response.status_code == 422


def test_dashboard_base_dir_falls_back_to_module_path():
    import dashboard

    with patch.object(dashboard, "_config", SimpleNamespace()):
        assert dashboard._dashboard_base_dir() == Path(dashboard.__file__).resolve().parent


@pytest.mark.asyncio
async def test_category_stats_uses_content_feedback_not_missing_trends_column(tmp_path):
    import aiosqlite
    import dashboard

    recent_at = (datetime.now() - timedelta(hours=1)).isoformat()
    conn = await aiosqlite.connect(tmp_path / "dashboard.db")
    conn.row_factory = aiosqlite.Row
    await dashboard.init_db(conn)
    cursor = await conn.execute(
        "INSERT INTO runs(run_uuid, started_at, country) VALUES (?, ?, ?)",
        ("live-test", recent_at, "korea"),
    )
    run_id = cursor.lastrowid
    await conn.execute(
        "INSERT INTO trends(run_id, keyword, viral_potential, scored_at) VALUES (?, ?, ?, ?)",
        (run_id, "AI 콘텐츠", 91, recent_at),
    )
    await conn.execute(
        "INSERT INTO content_feedback(keyword, category, created_at) VALUES (?, ?, ?)",
        ("AI 콘텐츠", "테크", recent_at),
    )
    await conn.commit()

    with (
        patch.object(dashboard, "_get_conn", AsyncMock(return_value=conn)),
        patch.object(dashboard, "_close_conn", AsyncMock()),
    ):
        response = await dashboard.api_category_stats(days=7)

    assert json.loads(response.body) == [
        {"category": "테크", "count": 1, "avg_score": 91.0, "max_score": 91, "min_score": 91}
    ]
    await conn.close()
