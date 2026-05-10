"""Tests for external research enrichment (OpenAlex + CrossRef)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BIOLINKER_DIR = Path(__file__).resolve().parent.parent
if str(BIOLINKER_DIR) not in sys.path:
    sys.path.insert(0, str(BIOLINKER_DIR))

from services.external_research import (  # noqa: E402
    ExternalResearchClient,
    ScholarlyWork,
    _reconstruct_abstract,
)


def test_reconstruct_abstract_orders_words_by_position() -> None:
    inverted = {"hello": [1], "world": [2], "say": [0]}
    assert _reconstruct_abstract(inverted) == "say hello world"


def test_reconstruct_abstract_handles_empty() -> None:
    assert _reconstruct_abstract(None) == ""
    assert _reconstruct_abstract({}) == ""


def test_scholarly_work_to_dict_has_stable_keys() -> None:
    work = ScholarlyWork(source="openalex", id="W123", title="t")
    payload = work.to_dict()
    expected_keys = {
        "source", "id", "title", "doi", "year", "citation_count",
        "authors", "venue", "abstract", "concepts", "open_access_url",
    }
    assert expected_keys <= payload.keys()


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakeSession:
    def __init__(self, openalex_payload: dict, crossref_payload: dict) -> None:
        self._openalex = openalex_payload
        self._crossref = crossref_payload
        self.calls: list[str] = []

    async def get(self, url: str, params: dict | None = None) -> _FakeResponse:
        self.calls.append(url)
        if "openalex.org" in url:
            return _FakeResponse(self._openalex)
        return _FakeResponse(self._crossref)

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_search_openalex_normalizes_results() -> None:
    payload = {
        "results": [
            {
                "id": "https://openalex.org/W42",
                "title": "Bio AI for drug discovery",
                "doi": "https://doi.org/10.1/abc",
                "publication_year": 2024,
                "cited_by_count": 17,
                "authorships": [{"author": {"display_name": "Jane Doe"}}],
                "concepts": [
                    {"display_name": "AI", "score": 0.8},
                    {"display_name": "Noise", "score": 0.1},
                ],
                "primary_location": {"source": {"display_name": "Nature"}},
                "open_access": {"oa_url": "https://example.org/pdf"},
                "abstract_inverted_index": {"AI": [1], "We": [0], "drug": [2]},
            }
        ]
    }
    fake = _FakeSession(openalex_payload=payload, crossref_payload={})
    client = ExternalResearchClient(session=fake)  # type: ignore[arg-type]

    works = await client.search_openalex("ai drug")
    assert len(works) == 1
    work = works[0]
    assert work.id == "W42"
    assert work.doi == "10.1/abc"
    assert work.year == 2024
    assert work.citation_count == 17
    assert work.authors == ["Jane Doe"]
    assert "AI" in work.concepts and "Noise" not in work.concepts
    assert work.venue == "Nature"
    assert work.open_access_url.endswith("/pdf")
    assert work.abstract == "We AI drug"


@pytest.mark.asyncio
async def test_lookup_crossref_doi_normalizes_message() -> None:
    payload = {
        "message": {
            "title": ["Trial"],
            "author": [{"given": "A", "family": "B"}],
            "issued": {"date-parts": [[2023, 1]]},
            "container-title": ["Cell"],
            "is-referenced-by-count": 5,
            "subject": ["biotech", "AI"],
            "abstract": "  test  ",
        }
    }
    fake = _FakeSession(openalex_payload={}, crossref_payload=payload)
    client = ExternalResearchClient(session=fake)  # type: ignore[arg-type]

    work = await client.lookup_crossref_doi("10.1/xyz")
    assert work is not None
    assert work.title == "Trial"
    assert work.year == 2023
    assert work.authors == ["A B"]
    assert work.venue == "Cell"
    assert work.citation_count == 5
    assert work.concepts == ["biotech", "AI"]
    assert work.abstract == "test"


@pytest.mark.asyncio
async def test_enrich_query_runs_concurrently_and_aggregates() -> None:
    payload_oa = {
        "results": [
            {
                "id": "https://openalex.org/W1",
                "title": "x",
                "doi": "",
                "cited_by_count": 3,
            }
        ]
    }
    payload_cr = {
        "message": {
            "title": ["y"],
            "is-referenced-by-count": 7,
            "issued": {"date-parts": [[2022]]},
        }
    }
    fake = _FakeSession(openalex_payload=payload_oa, crossref_payload=payload_cr)
    client = ExternalResearchClient(session=fake)  # type: ignore[arg-type]

    bundle = await client.enrich_query(
        "topic", per_page=5, crossref_dois=["10.1/zzz"]
    )
    assert bundle["query"] == "topic"
    assert len(bundle["openalex"]) == 1
    assert len(bundle["crossref"]) == 1
    assert bundle["total_citations"] == 10
