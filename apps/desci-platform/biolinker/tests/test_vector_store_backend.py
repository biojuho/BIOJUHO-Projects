"""
Tests for vector store backend selection.
"""
from __future__ import annotations

import services.vector_store as vector_store_module


def test_get_vector_store_uses_qdrant_when_enabled(monkeypatch):
    """Backend selector should instantiate QdrantVectorStore when configured."""
    sentinel = object()

    monkeypatch.setenv("VECTOR_STORE_BACKEND", "qdrant")
    monkeypatch.setattr(vector_store_module, "_load_qdrant_support", lambda: True)
    monkeypatch.setattr(vector_store_module, "_VECTOR_STORE", None)
    monkeypatch.setattr(vector_store_module, "QdrantVectorStore", lambda: sentinel)

    store = vector_store_module.get_vector_store()

    assert store is sentinel


def test_get_vector_store_falls_back_to_chroma_when_qdrant_unavailable(monkeypatch):
    """Backend selector should fall back to VectorStore if qdrant-client is unavailable."""

    class StubChromaStore:
        pass

    monkeypatch.setenv("VECTOR_STORE_BACKEND", "qdrant")
    monkeypatch.setattr(vector_store_module, "_load_qdrant_support", lambda: False)
    monkeypatch.setattr(vector_store_module, "_VECTOR_STORE", None)
    monkeypatch.setattr(vector_store_module, "VectorStore", StubChromaStore)

    store = vector_store_module.get_vector_store()

    assert isinstance(store, StubChromaStore)
