"""Regression tests for agent_graph nodes (collector + matcher).

These cover the wiring added on top of the pre-existing analyzer/proposal
LLM logic — we mock the LLM client and only assert that the collector and
matcher invoke their dependencies and shape state correctly.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from services import agent_graph
from models import RFPDocument


@pytest.mark.asyncio
async def test_collector_parses_plain_text(monkeypatch):
    parsed = RFPDocument(
        id="rfp-1",
        title="AI 신약 개발 공고",
        source="KDDF",
        body_text="대화체 본문",
        keywords=["AI", "신약"],
        url=None,
    )

    fake_crawler = MagicMock()
    fake_crawler.parse_text = AsyncMock(return_value=parsed)
    fake_crawler.fetch_url = AsyncMock()
    monkeypatch.setattr("services.crawler.get_crawler", lambda: fake_crawler)

    state = await agent_graph.collector_node(
        {"rfp_text": "대화체 본문", "user_profile": {}, "errors": [], "current_step": "init"}
    )

    fake_crawler.parse_text.assert_awaited_once()
    fake_crawler.fetch_url.assert_not_called()
    assert state["current_step"] == "collecting"
    assert state["collected_notices"][0]["id"] == "rfp-1"
    assert state["collected_notices"][0]["source"] == "KDDF"


@pytest.mark.asyncio
async def test_collector_fetches_url_when_input_is_link(monkeypatch):
    parsed = RFPDocument(
        id="rfp-2",
        title="크롤된 공고",
        source="NTIS",
        body_text="원격 본문",
        url="https://example.com/notice",
    )
    fake_crawler = MagicMock()
    fake_crawler.fetch_url = AsyncMock(return_value=parsed)
    fake_crawler.parse_text = AsyncMock()
    monkeypatch.setattr("services.crawler.get_crawler", lambda: fake_crawler)

    state = await agent_graph.collector_node(
        {"rfp_text": "https://example.com/notice", "user_profile": {}, "errors": [], "current_step": "init"}
    )

    fake_crawler.fetch_url.assert_awaited_once_with("https://example.com/notice")
    fake_crawler.parse_text.assert_not_called()
    assert state["collected_notices"][0]["url"] == "https://example.com/notice"


@pytest.mark.asyncio
async def test_collector_appends_ntis_notices_when_keyword_present(monkeypatch):
    parsed = RFPDocument(id="rfp-3", title="t", source="x", body_text="b")
    fake_crawler = MagicMock()
    fake_crawler.parse_text = AsyncMock(return_value=parsed)
    fake_crawler.fetch_url = AsyncMock()
    monkeypatch.setattr("services.crawler.get_crawler", lambda: fake_crawler)

    fake_ntis_instance = MagicMock()
    fake_ntis_instance.fetch_notice_list = AsyncMock(
        return_value=[{"id": "n-1", "title": "NTIS 공고", "url": "https://ntis/n-1", "body_text": "ntis 본문"}]
    )
    fake_ntis_instance.close = AsyncMock()
    monkeypatch.setattr("services.ntis_crawler.NTISCrawler", lambda: fake_ntis_instance)

    state = await agent_graph.collector_node(
        {
            "rfp_text": "본문",
            "user_profile": {"ntis_keyword": "바이오"},
            "errors": [],
            "current_step": "init",
        }
    )

    fake_ntis_instance.fetch_notice_list.assert_awaited_once_with(keyword="바이오")
    sources = [n["source"] for n in state["collected_notices"]]
    assert "NTIS" in sources
    assert len(state["collected_notices"]) == 2


@pytest.mark.asyncio
async def test_collector_records_error_when_crawler_fails(monkeypatch):
    fake_crawler = MagicMock()
    fake_crawler.parse_text = AsyncMock(side_effect=RuntimeError("boom"))
    fake_crawler.fetch_url = AsyncMock()
    monkeypatch.setattr("services.crawler.get_crawler", lambda: fake_crawler)

    state = await agent_graph.collector_node(
        {"rfp_text": "본문", "user_profile": {}, "errors": [], "current_step": "init"}
    )

    assert state["collected_notices"], "fallback notice should still exist"
    assert state["collected_notices"][0]["source"] == "direct_input"
    assert any("crawler_parse_failed" in e for e in state["errors"])


@pytest.mark.asyncio
async def test_matcher_uses_vector_store_and_vc_crawler(monkeypatch):
    doc = RFPDocument(id="p-1", title="paper", source="KDDF", body_text="b")
    fake_store = MagicMock()
    fake_store.search_similar.return_value = [(doc, 0.87)]
    fake_store.search_by_profile.return_value = [{**doc.model_dump(), "similarity_score": 0.91}]

    class _FakeStoreCtor:
        def __call__(self, *a, **k):
            return fake_store

    monkeypatch.setattr("services.vector_store.VectorStore", _FakeStoreCtor())

    vc = MagicMock()
    vc.model_dump.return_value = {
        "id": "vc-1",
        "name": "Bio Capital",
        "portfolio_keywords": ["Oncology", "AI"],
    }
    fake_vc_crawler = MagicMock()
    fake_vc_crawler.fetch_vc_list.return_value = [vc]
    monkeypatch.setattr("services.vc_crawler.VCCrawler", lambda: fake_vc_crawler)

    state = await agent_graph.matcher_node(
        {
            "rfp_text": "본문",
            "user_profile": {"tech_keywords": ["AI", "oncology"], "tech_description": "AI drug discovery"},
            "fit_score": 80,
            "fit_grade": "A",
            "collected_notices": [],
            "errors": [],
            "current_step": "analyzing",
        }
    )

    assert state["current_step"] == "matching"
    assert state["matched_papers"], "vector store path should populate matched_papers"
    assert state["matched_papers"][0]["similarity_score"] == pytest.approx(0.91)
    assert state["matched_vcs"][0]["id"] == "vc-1"
    assert state["matched_vcs"][0]["match_score"] >= 1.0
    fake_store.search_by_profile.assert_called_once()
    fake_vc_crawler.fetch_vc_list.assert_called_once()


@pytest.mark.asyncio
async def test_matcher_degrades_gracefully_when_store_unavailable(monkeypatch):
    class _Boom:
        def __init__(self, *a, **k):
            raise RuntimeError("no chromadb")

    monkeypatch.setattr("services.vector_store.VectorStore", _Boom)

    fake_vc_crawler = MagicMock()
    fake_vc_crawler.fetch_vc_list.return_value = []
    monkeypatch.setattr("services.vc_crawler.VCCrawler", lambda: fake_vc_crawler)

    state = await agent_graph.matcher_node(
        {
            "rfp_text": "본문",
            "user_profile": {},
            "errors": [],
            "current_step": "analyzing",
        }
    )

    assert state["matched_papers"] == []
    assert state["matched_vcs"] == []
    assert any("paper_search_failed" in e for e in state["errors"])
