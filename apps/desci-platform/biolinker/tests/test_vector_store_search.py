"""
Tests for hybrid reranking and metadata filtering in the vector store.
"""
from __future__ import annotations

from datetime import datetime

import services.vector_store as vector_store_module


def _seed_notice(store, doc_id: str, title: str, source: str, keywords: str, document: str, deadline: str, min_trl: int, max_trl: int):
    store._save_to_json(  # pylint: disable=protected-access
        doc_id,
        [1.0, 0.0],
        {
            "title": title,
            "source": source,
            "keywords": keywords,
            "deadline": deadline,
            "min_trl": min_trl,
            "max_trl": max_trl,
            "created_at": datetime.now().isoformat(),
        },
        document,
    )


def test_search_similar_hybrid_reranks_lexical_matches(monkeypatch, tmp_path):
    """Lexical overlap should break vector-score ties in favor of the better text match."""
    monkeypatch.setattr(vector_store_module, "CHROMADB_AVAILABLE", False)
    store = vector_store_module.VectorStore(persist_dir=str(tmp_path))
    monkeypatch.setattr(store, "_get_embedding", lambda text: [1.0, 0.0])

    _seed_notice(
        store,
        "rfp-ai-drug",
        "AI Drug Discovery Grant",
        "KDDF",
        "ai,drug discovery,platform",
        "Funding for AI-guided drug discovery and translational validation.",
        "2026-06-01T00:00:00",
        3,
        5,
    )
    _seed_notice(
        store,
        "rfp-marine",
        "Marine Logistics Support Program",
        "NTIS",
        "shipping,ports,logistics",
        "Support for marine logistics optimization and port infrastructure.",
        "2026-08-01T00:00:00",
        3,
        5,
    )

    results = store.search_similar("AI drug discovery", n_results=2)

    assert len(results) == 2
    assert results[0][0].id == "rfp-ai-drug"
    assert results[0][1] > results[1][1]


def test_search_similar_applies_metadata_filters(monkeypatch, tmp_path):
    """Structured filters should keep only notices matching source, keyword, deadline, and TRL."""
    monkeypatch.setattr(vector_store_module, "CHROMADB_AVAILABLE", False)
    store = vector_store_module.VectorStore(persist_dir=str(tmp_path))
    monkeypatch.setattr(store, "_get_embedding", lambda text: [1.0, 0.0])

    _seed_notice(
        store,
        "rfp-match",
        "AI Drug Discovery Grant",
        "KDDF",
        "ai,drug discovery,platform",
        "Funding for AI-guided drug discovery and translational validation.",
        "2026-06-01T00:00:00",
        3,
        5,
    )
    _seed_notice(
        store,
        "rfp-too-late",
        "AI Platform Expansion",
        "KDDF",
        "ai,platform",
        "Late-stage platform expansion program.",
        "2027-02-01T00:00:00",
        3,
        5,
    )
    _seed_notice(
        store,
        "rfp-wrong-source",
        "AI Drug Discovery Grant",
        "NTIS",
        "ai,drug discovery",
        "Similar language but different source.",
        "2026-06-01T00:00:00",
        3,
        5,
    )

    results = store.search_similar(
        "AI drug discovery",
        n_results=5,
        filters={
            "source": "KDDF",
            "keyword": "drug",
            "deadline_to": "2026-12-31T23:59:59",
            "trl_min": 3,
            "trl_max": 5,
        },
    )

    assert len(results) == 1
    assert results[0][0].id == "rfp-match"
