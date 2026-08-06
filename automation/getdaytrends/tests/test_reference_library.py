"""Tests for the local creator reference library."""

import json
import sys
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
async def test_live_collector_creates_and_refreshes_youtube_metadata(tmp_path):
    store = ReferenceLibraryStore(tmp_path / "live-library.json")
    collector = YouTubeLiveReferenceCollector(store, executable="/fake/yt-dlp")
    collector._search_keyword = AsyncMock(
        return_value=[
            {
                "id": "live123",
                "title": "지금 뜨는 AI 콘텐츠",
                "url": "https://www.youtube.com/watch?v=live123",
                "channel": "라이브 채널",
                "duration": 58,
                "view_count": 125_000,
            }
        ]
    )

    first = await collector.refresh(["AI 콘텐츠"], per_keyword=3)
    assert first["collected"] == 1
    assert first["created"] == 1
    assert first["updated"] == 0
    item = store.list()[0]
    assert item["content_format"] == "short"
    assert item["recommendation_score"] >= 80
    assert "조회수 125,000" in item["caption"]

    store.update(item["id"], ReferenceItemPatch(saved=True, memo="사용자 메모 유지"))
    second = await collector.refresh(["AI 콘텐츠"], per_keyword=3)
    assert second["created"] == 0
    assert second["updated"] == 1
    refreshed = store.get(item["id"])
    assert refreshed["saved"] is True
    assert refreshed["memo"] == "사용자 메모 유지"
    assert store.get_live_status()["source"] == "youtube"


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
    assert "force_refresh: !silent" in response.text
    assert "Threads 검색" in response.text
    assert "커뮤니티 바이럴 조기감지" in response.text
    assert "/api/fast-viral/refresh" in response.text


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

    conn = await aiosqlite.connect(tmp_path / "dashboard.db")
    conn.row_factory = aiosqlite.Row
    await dashboard.init_db(conn)
    cursor = await conn.execute(
        "INSERT INTO runs(run_uuid, started_at, country) VALUES (?, ?, ?)",
        ("live-test", "2026-08-05T00:00:00", "korea"),
    )
    run_id = cursor.lastrowid
    await conn.execute(
        "INSERT INTO trends(run_id, keyword, viral_potential, scored_at) VALUES (?, ?, ?, ?)",
        (run_id, "AI 콘텐츠", 91, "2026-08-05T00:00:00"),
    )
    await conn.execute(
        "INSERT INTO content_feedback(keyword, category, created_at) VALUES (?, ?, ?)",
        ("AI 콘텐츠", "테크", "2026-08-05T00:00:00"),
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
