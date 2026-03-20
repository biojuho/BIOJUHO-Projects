"""
Unit tests for asset upload parsing and indexing behavior.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import services.asset_manager as asset_manager_module


class StubUploadFile:
    def __init__(self, filename: str, content: bytes) -> None:
        self.filename = filename
        self._content = content

    async def read(self) -> bytes:
        return self._content


@pytest.mark.asyncio
async def test_upload_asset_uses_parser_metadata(monkeypatch, tmp_path):
    """Structured parser output should feed indexing metadata and response analysis."""
    parse_result = SimpleNamespace(
        text="Structured body text",
        metadata={
            "title": "Detected Paper Title",
            "abstract": "Detected abstract",
            "keywords": ["crispr", "delivery"],
            "doi": "10.1000/example",
            "authors": [{"name": "Jane Doe"}],
        },
        parser="grobid",
    )
    stub_parser = SimpleNamespace(parse_document=lambda content, filename="document.pdf": parse_result)

    captured: dict[str, object] = {}

    class StubVectorStore:
        def add_company_asset(self, asset_id, title, content, metadata):
            captured["asset_id"] = asset_id
            captured["title"] = title
            captured["content"] = content
            captured["metadata"] = metadata

    monkeypatch.setattr(asset_manager_module, "get_pdf_parser", lambda: stub_parser)
    monkeypatch.setattr(asset_manager_module, "get_vector_store", lambda: StubVectorStore())

    manager = asset_manager_module.AssetManager(asset_dir=str(tmp_path))
    result = await manager.upload_asset(StubUploadFile("paper.pdf", b"%PDF-1.4 test"), asset_type="paper")

    assert result["indexed"] is True
    assert result["analysis"]["parser"] == "grobid"
    assert captured["title"] == "Detected Paper Title"
    assert captured["metadata"]["doi"] == "10.1000/example"


@pytest.mark.asyncio
async def test_upload_paper_indexes_structured_metadata(monkeypatch, tmp_path):
    """Paper uploads should merge parser output, pin metadata, and index user-scoped records."""
    parse_result = SimpleNamespace(
        text="Structured paper body",
        metadata={
            "title": "Structured Title",
            "abstract": "Structured abstract",
            "keywords": ["gene editing", "delivery"],
            "doi": "10.1000/paper",
            "authors": [
                {"name": "Jane Doe", "affiliation": "Bio Lab"},
                {"name": "John Roe", "affiliation": "Bio Lab"},
            ],
            "references": ["Reference A", "Reference B"],
        },
        parser="grobid",
    )
    stub_parser = SimpleNamespace(parse_document=lambda content, filename="document.pdf": parse_result)

    class StubIPFS:
        async def upload_file(self, file_path: str, metadata: dict):
            captured["file_path"] = file_path
            captured["ipfs_metadata"] = metadata
            return {
                "cid": "QmStructuredPaper123",
                "url": "https://ipfs.io/ipfs/QmStructuredPaper123",
            }

    captured: dict[str, object] = {}

    class StubVectorStore:
        def add_paper(self, **kwargs):
            captured["paper"] = kwargs

    monkeypatch.setattr(asset_manager_module, "get_pdf_parser", lambda: stub_parser)
    monkeypatch.setattr(asset_manager_module, "get_vector_store", lambda: StubVectorStore())
    monkeypatch.setattr(asset_manager_module, "get_ipfs_service", lambda: StubIPFS())

    manager = asset_manager_module.AssetManager(asset_dir=str(tmp_path))
    result = await manager.upload_paper(
        StubUploadFile("paper.pdf", b"%PDF-1.4 test"),
        user={"uid": "user-123", "email": "user@example.com", "name": "Test User"},
        title="",
        authors="Manual Author",
        abstract="",
    )

    assert result["cid"] == "QmStructuredPaper123"
    assert result["title"] == "Structured Title"
    assert result["authors"] == ["Jane Doe", "John Roe"]
    assert result["analysis"]["reference_count"] == 2
    assert "doi" in result["analysis"]["structured_fields"]
    assert captured["paper"]["owner_uid"] == "user-123"
    assert captured["paper"]["doi"] == "10.1000/paper"
    assert captured["paper"]["affiliations"] == ["Bio Lab"]
    assert captured["paper"]["cid"] == "QmStructuredPaper123"
    assert captured["ipfs_metadata"]["owner_uid"] == "user-123"
