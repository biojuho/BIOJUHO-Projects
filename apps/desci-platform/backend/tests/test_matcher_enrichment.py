"""Tests for the RFPMatcher OpenAlex enrichment path."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

BIOLINKER_DIR = Path(__file__).resolve().parent.parent
if str(BIOLINKER_DIR) not in sys.path:
    sys.path.insert(0, str(BIOLINKER_DIR))


def test_extract_query_seed_collapses_whitespace_and_caps_length() -> None:
    from services.matcher import _extract_query_seed

    text = "AI drug   discovery   for   biomarker " * 100
    seed = _extract_query_seed(text, max_chars=80)
    assert len(seed) == 80
    assert "  " not in seed


def test_extract_query_seed_handles_empty() -> None:
    from services.matcher import _extract_query_seed

    assert _extract_query_seed("") == ""
    assert _extract_query_seed(None) == ""  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_collect_enrichment_concepts_ranks_by_frequency() -> None:
    from services.external_research import ScholarlyWork
    from services.matcher import _collect_enrichment_concepts

    fake_works = [
        ScholarlyWork(source="openalex", id="W1", title="t", concepts=["AI", "Biotech"]),
        ScholarlyWork(source="openalex", id="W2", title="t", concepts=["AI", "Genomics"]),
        ScholarlyWork(source="openalex", id="W3", title="t", concepts=["AI"]),
    ]

    fake_client = AsyncMock()
    fake_client.search_openalex = AsyncMock(return_value=fake_works)
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=None)

    with patch("services.matcher.ExternalResearchClient", return_value=fake_client):
        concepts = await _collect_enrichment_concepts("ai drug")

    # AI appears 3x → rank #1
    assert concepts[0] == "AI"
    assert set(concepts) == {"AI", "Biotech", "Genomics"}


@pytest.mark.asyncio
async def test_collect_enrichment_concepts_swallows_errors() -> None:
    from services.matcher import _collect_enrichment_concepts

    fake_client = AsyncMock()
    fake_client.__aenter__ = AsyncMock(side_effect=RuntimeError("network down"))
    fake_client.__aexit__ = AsyncMock(return_value=None)

    with patch("services.matcher.ExternalResearchClient", return_value=fake_client):
        concepts = await _collect_enrichment_concepts("anything")

    assert concepts == []


@pytest.mark.asyncio
async def test_match_paper_legacy_shape_unchanged_when_enrich_false() -> None:
    from services.matcher import RFPMatcher

    fake_doc = MagicMock()
    fake_doc.id = "rfp-1"
    fake_doc.source = "KDDF"
    fake_doc.body_text = "RFP body"
    fake_doc.title = "AI Drug Fund"
    fake_doc.keywords = ["ai", "drug"]
    fake_doc.min_trl = None
    fake_doc.max_trl = None

    fake_store = MagicMock()
    fake_store.get_notice = MagicMock(return_value={"document": "AI for drug discovery"})
    fake_store.search_similar = MagicMock(return_value=[(fake_doc, 0.91)])

    matcher = RFPMatcher.__new__(RFPMatcher)
    matcher.vector_store = fake_store

    result = await matcher.match_paper("paper-1", limit=5, enrich=False)
    assert isinstance(result, list)
    assert result[0]["id"] == "rfp-1"
    assert result[0]["similarity"] == 0.91


@pytest.mark.asyncio
async def test_match_paper_enrich_true_returns_enrichment_block_and_widens_query() -> None:
    from services.matcher import RFPMatcher

    fake_doc = MagicMock()
    fake_doc.id = "rfp-1"
    fake_doc.source = "KDDF"
    fake_doc.body_text = "RFP body"
    fake_doc.title = "AI Drug Fund"
    fake_doc.keywords = ["ai"]
    fake_doc.min_trl = None
    fake_doc.max_trl = None

    fake_store = MagicMock()
    fake_store.get_notice = MagicMock(return_value={"document": "Original paper text"})
    fake_store.search_similar = MagicMock(return_value=[(fake_doc, 0.8)])

    matcher = RFPMatcher.__new__(RFPMatcher)
    matcher.vector_store = fake_store

    with patch(
        "services.matcher._collect_enrichment_concepts",
        AsyncMock(return_value=["AI", "Biotech"]),
    ):
        result = await matcher.match_paper("paper-1", limit=5, enrich=True)

    assert isinstance(result, dict)
    assert result["enrichment"]["applied"] is True
    assert result["enrichment"]["concepts"] == ["AI", "Biotech"]
    assert result["enrichment"]["source"] == "openalex"
    assert len(result["matches"]) == 1

    # Verify the search query was widened with the concepts
    query_passed = fake_store.search_similar.call_args[0][0]
    assert "Original paper text" in query_passed
    assert "AI, Biotech" in query_passed


@pytest.mark.asyncio
async def test_match_paper_enrich_true_with_no_concepts_marks_not_applied() -> None:
    from services.matcher import RFPMatcher

    fake_store = MagicMock()
    fake_store.get_notice = MagicMock(return_value={"document": "x"})
    fake_store.search_similar = MagicMock(return_value=[])

    matcher = RFPMatcher.__new__(RFPMatcher)
    matcher.vector_store = fake_store

    with patch(
        "services.matcher._collect_enrichment_concepts",
        AsyncMock(return_value=[]),
    ):
        result = await matcher.match_paper("paper-1", limit=5, enrich=True)

    assert isinstance(result, dict)
    assert result["enrichment"]["applied"] is False
    assert result["enrichment"]["source"] is None
    assert result["matches"] == []
