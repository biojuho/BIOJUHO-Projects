"""
BioLinker - GROBID Parser Service

Optional integration with a local GROBID server for parsing scientific PDFs
into structured TEI XML and extracting richer metadata than pypdf alone.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover - exercised via import fallback
    httpx = None

from .logging_config import get_logger

log = get_logger("biolinker.services.grobid_parser")

TEI_NS = {"tei": "http://www.tei-c.org/ns/1.0"}


@dataclass
class GrobidParseResult:
    """Structured data returned from a successful GROBID parse."""

    text: str
    metadata: dict[str, Any]
    tei_xml: str


class GrobidParser:
    """Thin HTTP client for an optional GROBID service."""

    def __init__(self) -> None:
        self.enabled = os.getenv("GROBID_ENABLED", "false").lower() == "true"
        self.base_url = os.getenv("GROBID_URL", "http://grobid:8070/api").rstrip("/")
        self.timeout_seconds = float(os.getenv("GROBID_TIMEOUT_SECONDS", "60"))

    @property
    def is_configured(self) -> bool:
        """Whether GROBID integration is configured to be used."""
        return self.enabled and bool(self.base_url) and httpx is not None

    def health_check(self) -> bool:
        """Best-effort health probe against the configured GROBID instance."""
        if not self.is_configured:
            return False

        candidates = [
            f"{self.base_url}/isalive",
            f"{self.base_url.rsplit('/api', 1)[0]}/api/isalive",
            self.base_url,
        ]

        try:
            with httpx.Client(timeout=5.0) as client:
                for url in candidates:
                    try:
                        response = client.get(url)
                        if response.status_code == 200:
                            body = response.text.strip().lower()
                            if body in {"true", "ok"} or "<html" in body or body == "":
                                return True
                    except httpx.HTTPError:
                        continue
        except Exception as exc:  # pragma: no cover - defensive branch
            log.warning("grobid_healthcheck_failed", error=str(exc))

        return False

    def parse_document(self, file_content: bytes, filename: str = "document.pdf") -> GrobidParseResult | None:
        """Parse a PDF via GROBID and return extracted text and metadata."""
        if not self.is_configured:
            return None

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    f"{self.base_url}/processFulltextDocument",
                    files={"input": (filename, file_content, "application/pdf")},
                    data={
                        "consolidateHeader": "1",
                        "consolidateCitations": "1",
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("grobid_parse_failed", error=str(exc))
            return None

        tei_xml = response.text.strip()
        if not tei_xml:
            return None

        try:
            root = ElementTree.fromstring(tei_xml)
        except ElementTree.ParseError as exc:
            log.warning("grobid_tei_parse_failed", error=str(exc))
            return None

        return GrobidParseResult(
            text=self._extract_body_text(root),
            metadata=self._extract_metadata(root),
            tei_xml=tei_xml,
        )

    def _extract_body_text(self, root: ElementTree.Element) -> str:
        """Extract readable full-text content from TEI."""
        blocks: list[str] = []

        for node in root.findall(".//tei:text/tei:body//tei:head", TEI_NS):
            value = self._normalize_text(" ".join(node.itertext()))
            if value:
                blocks.append(value)

        for node in root.findall(".//tei:text/tei:body//tei:p", TEI_NS):
            value = self._normalize_text(" ".join(node.itertext()))
            if value:
                blocks.append(value)

        if blocks:
            return "\n\n".join(blocks)

        fallback = self._normalize_text(
            " ".join(root.findtext(".//tei:text", default="", namespaces=TEI_NS) for _ in [0])
        )
        return fallback

    def _extract_metadata(self, root: ElementTree.Element) -> dict[str, Any]:
        """Extract commonly useful scholarly metadata from TEI."""
        title = self._first_text(
            root,
            [
                ".//tei:titleStmt/tei:title",
                ".//tei:analytic/tei:title",
            ],
        )
        abstract_parts = [
            self._normalize_text(" ".join(node.itertext()))
            for node in root.findall(".//tei:profileDesc/tei:abstract//tei:p", TEI_NS)
        ]
        keywords = [
            self._normalize_text(" ".join(node.itertext()))
            for node in root.findall(".//tei:profileDesc//tei:keywords//tei:term", TEI_NS)
        ]
        authors = []
        for author in root.findall(".//tei:analytic/tei:author", TEI_NS):
            name_parts = [
                self._normalize_text(" ".join(node.itertext()))
                for node in author.findall(".//tei:forename", TEI_NS) + author.findall(".//tei:surname", TEI_NS)
            ]
            affiliation = self._normalize_text(
                " ".join(node.itertext()) for node in author.findall(".//tei:affiliation", TEI_NS)
            )
            clean_name = " ".join([part for part in name_parts if part])
            if clean_name:
                authors.append({"name": clean_name, "affiliation": affiliation})

        doi = self._first_text(
            root,
            [
                ".//tei:publicationStmt//tei:idno[@type='DOI']",
                ".//tei:sourceDesc//tei:idno[@type='DOI']",
            ],
        )

        references = []
        for ref in root.findall(".//tei:listBibl/tei:biblStruct", TEI_NS):
            ref_title = self._first_text(ref, [".//tei:title"])
            if ref_title:
                references.append(ref_title)

        metadata: dict[str, Any] = {
            "title": title,
            "abstract": " ".join([part for part in abstract_parts if part]).strip(),
            "keywords": [keyword for keyword in keywords if keyword],
            "authors": authors,
            "doi": doi,
            "references": references[:25],
        }
        return {key: value for key, value in metadata.items() if value}

    def _first_text(self, root: ElementTree.Element, selectors: list[str]) -> str:
        for selector in selectors:
            node = root.find(selector, TEI_NS)
            if node is None:
                continue
            text = self._normalize_text(" ".join(node.itertext()))
            if text:
                return text
        return ""

    @staticmethod
    def _normalize_text(value: Any) -> str:
        if isinstance(value, str):
            return " ".join(value.split())
        if value is None:
            return ""
        return " ".join(str(part) for part in value if str(part).strip()).strip()


_grobid_parser = GrobidParser()


def get_grobid_parser() -> GrobidParser:
    return _grobid_parser
