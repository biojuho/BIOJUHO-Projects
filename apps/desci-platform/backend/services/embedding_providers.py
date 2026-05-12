"""
BioLinker — Embedding Provider Loaders

Lazy-loaded embedding backends (Google Gemini, OpenAI, Qdrant).
Extracted from vector_store.py to isolate dependency management.
"""

import os
from typing import Any

# ── Conditional imports ────────────────────────────────

CHROMADB_AVAILABLE = False
try:
    import chromadb  # type: ignore  # noqa: F401

    CHROMADB_AVAILABLE = True
except Exception:  # pylint: disable=broad-exception-caught
    pass

OPENAI_AVAILABLE = False
OpenAI = None  # type: ignore
_OPENAI_LOAD_ATTEMPTED = False

_GOOGLE_AVAILABLE = False
GoogleGenerativeAIEmbeddings = None  # type: ignore
_GOOGLE_LOAD_ATTEMPTED = False

QDRANT_AVAILABLE = False
QdrantClient = None  # type: ignore
qdrant_models = None  # type: ignore
_QDRANT_LOAD_ATTEMPTED = False


def _load_openai_support() -> bool:
    global OPENAI_AVAILABLE, OpenAI, _OPENAI_LOAD_ATTEMPTED  # pylint: disable=global-statement
    if _OPENAI_LOAD_ATTEMPTED:
        return OPENAI_AVAILABLE

    _OPENAI_LOAD_ATTEMPTED = True
    try:
        from openai import OpenAI as _OpenAI  # type: ignore

        OpenAI = _OpenAI
        OPENAI_AVAILABLE = True
    except Exception:  # pylint: disable=broad-exception-caught
        OPENAI_AVAILABLE = False
    return OPENAI_AVAILABLE


def _load_google_support() -> bool:
    global _GOOGLE_AVAILABLE, GoogleGenerativeAIEmbeddings, _GOOGLE_LOAD_ATTEMPTED  # pylint: disable=global-statement
    if _GOOGLE_LOAD_ATTEMPTED:
        return _GOOGLE_AVAILABLE

    _GOOGLE_LOAD_ATTEMPTED = True
    try:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings as _GoogleEmbeddings  # type: ignore

        GoogleGenerativeAIEmbeddings = _GoogleEmbeddings
        _GOOGLE_AVAILABLE = True
    except Exception:  # pylint: disable=broad-exception-caught
        _GOOGLE_AVAILABLE = False
    return _GOOGLE_AVAILABLE


def _load_qdrant_support() -> bool:
    global QDRANT_AVAILABLE, QdrantClient, qdrant_models, _QDRANT_LOAD_ATTEMPTED  # pylint: disable=global-statement
    if _QDRANT_LOAD_ATTEMPTED:
        return QDRANT_AVAILABLE

    _QDRANT_LOAD_ATTEMPTED = True
    try:
        from qdrant_client import QdrantClient as _QdrantClient  # type: ignore

        QdrantClient = _QdrantClient
        try:
            from qdrant_client import models as _qdrant_models  # type: ignore
        except Exception:  # pylint: disable=broad-exception-caught
            from qdrant_client.http import models as _qdrant_models  # type: ignore
        qdrant_models = _qdrant_models
        QDRANT_AVAILABLE = True
    except Exception:  # pylint: disable=broad-exception-caught
        QDRANT_AVAILABLE = False
    return QDRANT_AVAILABLE


def init_embedding_fn(instance: Any) -> None:
    """Initialise embedding function on a VectorStore instance.

    Sets ``embedding_fn``, ``embedding_model``, and ``openai_client``
    attributes based on available providers (Google first, OpenAI fallback).
    """
    instance.embedding_fn = None
    instance.embedding_model = None
    instance.openai_client = None

    google_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if google_key and _load_google_support():
        instance.embedding_model = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001", google_api_key=google_key
        )
        instance.embedding_fn = instance._google_embedding_fn  # noqa: SLF001
    elif os.getenv("OPENAI_API_KEY") and _load_openai_support():
        instance.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        instance.embedding_fn = instance._openai_embedding_fn  # noqa: SLF001
