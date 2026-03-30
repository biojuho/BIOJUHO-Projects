"""
BioLinker - PDF Parser Service
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

import pypdf

from .grobid_parser import get_grobid_parser
from .logging_config import get_logger

log = get_logger("biolinker.services.pdf_parser")


@dataclass
class PDFParseResult:
    """Normalized parse result for both GROBID and pypdf fallback."""

    text: str
    metadata: dict[str, Any]
    parser: str


class PDFParser:
    """PDF 파일 텍스트 추출 서비스"""

    def __init__(self) -> None:
        self.grobid_parser = get_grobid_parser()

    def parse_document(self, file_content: bytes, filename: str = "document.pdf") -> PDFParseResult:
        """
        PDF 바이트 콘텐츠를 파싱해 텍스트와 메타데이터를 함께 반환한다.
        """
        grobid_result = self.grobid_parser.parse_document(file_content, filename=filename)
        if grobid_result and grobid_result.text.strip():
            return PDFParseResult(
                text=grobid_result.text,
                metadata=grobid_result.metadata,
                parser="grobid",
            )

        if grobid_result is None and self.grobid_parser.is_configured:
            log.info("pdf_parser_fallback_to_pypdf", reason="grobid_unavailable_or_failed")

        text = self._parse_with_pypdf(file_content)
        metadata = self._extract_metadata_with_pypdf(file_content)
        return PDFParseResult(text=text, metadata=metadata, parser="pypdf")

    def parse(self, file_content: bytes, filename: str = "document.pdf") -> str:
        """
        PDF 바이트 콘텐츠에서 텍스트 추출
        """
        return self.parse_document(file_content, filename=filename).text

    def extract_metadata(self, file_content: bytes, filename: str = "document.pdf") -> dict[str, Any]:
        """
        PDF 메타데이터 추출
        """
        return self.parse_document(file_content, filename=filename).metadata

    @staticmethod
    def _parse_with_pypdf(file_content: bytes) -> str:
        try:
            file_stream = io.BytesIO(file_content)
            reader = pypdf.PdfReader(file_stream)

            text: list[str] = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text.append(page_text)

            return "\n".join(text)
        except Exception as exc:
            log.warning("pypdf_parse_failed", error=str(exc))
            return ""

    @staticmethod
    def _extract_metadata_with_pypdf(file_content: bytes) -> dict[str, Any]:
        try:
            file_stream = io.BytesIO(file_content)
            reader = pypdf.PdfReader(file_stream)
            raw_metadata = reader.metadata or {}
            return {str(key): value for key, value in dict(raw_metadata).items()}
        except Exception:
            return {}


_parser = PDFParser()


def get_pdf_parser():
    return _parser
