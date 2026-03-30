import os
import uuid
from datetime import datetime
from typing import Any

from fastapi import UploadFile

from .ipfs_service import PaperMetadata, get_ipfs_service
from .pdf_parser import get_pdf_parser
from .vector_store import get_vector_store


class AssetManager:
    """Manage uploaded assets and structured paper indexing."""

    def __init__(self, asset_dir: str = "data/assets"):
        self.asset_dir = asset_dir
        os.makedirs(self.asset_dir, exist_ok=True)
        self.vector_store = get_vector_store()
        self.pdf_parser = get_pdf_parser()
        self.ipfs_service = get_ipfs_service()

    def _save_upload(self, file: UploadFile, content: bytes) -> tuple[str, str, str]:
        """Persist the uploaded file locally and return identifiers."""
        asset_id = str(uuid.uuid4())
        file_ext = os.path.splitext(file.filename)[1]
        saved_filename = f"{asset_id}{file_ext}"
        file_path = os.path.join(self.asset_dir, saved_filename)

        with open(file_path, "wb") as f:
            f.write(content)

        return asset_id, file_ext, file_path

    def _extract_text_and_metadata(
        self,
        file: UploadFile,
        file_ext: str,
        content: bytes,
    ) -> tuple[str, dict[str, Any], str]:
        """Parse uploaded content and return extracted text and metadata."""
        text_content = ""
        parsed_metadata: dict[str, Any] = {}
        parser_name = "none"

        if file_ext.lower() == ".pdf":
            if hasattr(self.pdf_parser, "parse_document"):
                parse_result = self.pdf_parser.parse_document(content, filename=file.filename)
                text_content = parse_result.text
                parsed_metadata = parse_result.metadata
                parser_name = parse_result.parser
            else:
                # Backward compatible path for tests that stub only `.parse()`
                text_content = self.pdf_parser.parse(content)
                parser_name = "stub"
        else:
            try:
                text_content = content.decode("utf-8")
                parser_name = "utf8"
            except (UnicodeDecodeError, AttributeError):
                text_content = ""

        return text_content, parsed_metadata, parser_name

    @staticmethod
    def _split_csv(raw_value: str) -> list[str]:
        return [item.strip() for item in raw_value.split(",") if item.strip()]

    def _resolve_paper_fields(
        self,
        file: UploadFile,
        submitted_title: str,
        submitted_authors: str,
        submitted_abstract: str,
        parsed_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """Merge submitted paper fields with parser-derived metadata."""
        parsed_authors = parsed_metadata.get("authors") or []
        author_names = [
            author.get("name", "").strip()
            for author in parsed_authors
            if isinstance(author, dict) and author.get("name")
        ]
        if not author_names:
            author_names = self._split_csv(submitted_authors)

        affiliations = []
        for author in parsed_authors:
            affiliation = ""
            if isinstance(author, dict):
                affiliation = str(author.get("affiliation") or "").strip()
            if affiliation and affiliation not in affiliations:
                affiliations.append(affiliation)

        references = [
            str(reference).strip() for reference in parsed_metadata.get("references", []) if str(reference).strip()
        ]
        keywords = [str(keyword).strip() for keyword in parsed_metadata.get("keywords", []) if str(keyword).strip()]

        final_title = (
            (submitted_title or "").strip() or str(parsed_metadata.get("title") or "").strip() or file.filename
        )
        final_abstract = (submitted_abstract or "").strip() or str(parsed_metadata.get("abstract") or "").strip()

        return {
            "title": final_title,
            "abstract": final_abstract,
            "authors": author_names,
            "affiliations": affiliations,
            "references": references,
            "keywords": keywords,
            "doi": str(parsed_metadata.get("doi") or "").strip(),
            "detected_title": str(parsed_metadata.get("title") or "").strip(),
        }

    async def upload_asset(self, file: UploadFile, asset_type: str = "general") -> dict[str, Any]:
        """
        Upload a generic asset and index extracted text.

        Args:
            file: Uploaded file object.
            asset_type: Asset subtype (ir, patent, paper, etc.)

        Returns:
            Upload result metadata.
        """
        content = await file.read()
        asset_id, file_ext, _file_path = self._save_upload(file, content)
        text_content, parsed_metadata, parser_name = self._extract_text_and_metadata(file, file_ext, content)

        extracted_text = bool(text_content)
        if not text_content:
            text_content = "No text content extracted."

        authors = parsed_metadata.get("authors") or []
        metadata = {
            "type": "company_asset",
            "asset_type": asset_type,
            "original_filename": file.filename,
            "uploaded_at": datetime.now().isoformat(),
            "source": "UserUpload",
            "parser": parser_name,
        }

        if parsed_metadata.get("title"):
            metadata["detected_title"] = parsed_metadata["title"]
        if parsed_metadata.get("abstract"):
            metadata["abstract"] = parsed_metadata["abstract"]
        if parsed_metadata.get("keywords"):
            metadata["keywords"] = ",".join(parsed_metadata["keywords"])
        if parsed_metadata.get("doi"):
            metadata["doi"] = parsed_metadata["doi"]
        if authors:
            metadata["authors"] = ", ".join(author.get("name", "").strip() for author in authors if author.get("name"))

        self.vector_store.add_company_asset(
            asset_id=asset_id,
            title=parsed_metadata.get("title") or file.filename,
            content=text_content,
            metadata=metadata,
        )

        return {
            "id": asset_id,
            "filename": file.filename,
            "type": asset_type,
            "size": len(content),
            "indexed": extracted_text,
            "analysis": {
                "status": "indexed" if extracted_text else "no_text",
                "parser": parser_name,
                "text_length": len(text_content) if extracted_text else 0,
                "metadata_keys": sorted(parsed_metadata.keys()),
            },
        }

    async def upload_paper(
        self,
        file: UploadFile,
        user: dict[str, Any],
        title: str = "",
        authors: str = "",
        abstract: str = "",
    ) -> dict[str, Any]:
        """Upload a research paper, pin it to IPFS, and index structured metadata."""
        content = await file.read()
        fallback_id, file_ext, file_path = self._save_upload(file, content)
        text_content, parsed_metadata, parser_name = self._extract_text_and_metadata(file, file_ext, content)

        extracted_text = bool(text_content)
        if not text_content:
            text_content = "No text content extracted."

        resolved_fields = self._resolve_paper_fields(
            file=file,
            submitted_title=title,
            submitted_authors=authors,
            submitted_abstract=abstract,
            parsed_metadata=parsed_metadata,
        )
        created_at = datetime.now().isoformat()

        ipfs_metadata = PaperMetadata(
            title=resolved_fields["title"],
            authors=resolved_fields["authors"],
            abstract=resolved_fields["abstract"],
            keywords=resolved_fields["keywords"],
            doi=resolved_fields["doi"] or None,
        ).to_dict()
        if resolved_fields["affiliations"]:
            ipfs_metadata["affiliations"] = resolved_fields["affiliations"]
        if resolved_fields["references"]:
            ipfs_metadata["references"] = resolved_fields["references"]
        if user.get("uid"):
            ipfs_metadata["owner_uid"] = user["uid"]

        upload_result = await self.ipfs_service.upload_file(file_path, metadata=ipfs_metadata)
        paper_id = str(upload_result.get("cid") or fallback_id)
        ipfs_url = str(upload_result.get("url") or "")

        self.vector_store.add_paper(
            paper_id=paper_id,
            title=resolved_fields["title"],
            abstract=resolved_fields["abstract"],
            full_text=text_content,
            keywords=resolved_fields["keywords"],
            authors=resolved_fields["authors"],
            affiliations=resolved_fields["affiliations"],
            references=resolved_fields["references"],
            doi=resolved_fields["doi"] or None,
            parser=parser_name,
            owner_uid=user.get("uid"),
            owner_email=user.get("email"),
            owner_name=user.get("name"),
            cid=paper_id,
            ipfs_url=ipfs_url,
            created_at=created_at,
        )

        return {
            "id": paper_id,
            "cid": paper_id,
            "filename": file.filename,
            "title": resolved_fields["title"],
            "abstract": resolved_fields["abstract"],
            "authors": resolved_fields["authors"],
            "affiliations": resolved_fields["affiliations"],
            "keywords": resolved_fields["keywords"],
            "doi": resolved_fields["doi"],
            "ipfs_url": ipfs_url,
            "type": "paper",
            "nft_minted": False,
            "created_at": created_at,
            "indexed": extracted_text,
            "analysis": {
                "status": "indexed" if extracted_text else "no_text",
                "parser": parser_name,
                "text_length": len(text_content) if extracted_text else 0,
                "metadata_keys": sorted(parsed_metadata.keys()),
                "reference_count": len(resolved_fields["references"]),
                "structured_fields": [
                    field_name
                    for field_name in ["title", "abstract", "authors", "affiliations", "references", "doi"]
                    if resolved_fields.get(field_name)
                ],
            },
        }

    def list_user_papers(self, user_id: str) -> list[dict[str, Any]]:
        """Return papers indexed for a specific authenticated user."""
        if not user_id:
            return []

        if hasattr(self.vector_store, "get_documents_by_metadata"):
            raw_items = self.vector_store.get_documents_by_metadata("owner_uid", user_id)
        else:
            raw_items = []

        papers = []
        for item in raw_items:
            metadata = item.get("metadata", {}) or {}
            papers.append(
                {
                    "id": item.get("id"),
                    "title": metadata.get("title", "Untitled paper"),
                    "abstract": metadata.get("abstract", ""),
                    "authors": self._split_csv(str(metadata.get("authors", ""))),
                    "affiliations": [
                        entry.strip() for entry in str(metadata.get("affiliations", "")).split(" | ") if entry.strip()
                    ],
                    "keywords": self._split_csv(str(metadata.get("keywords", ""))),
                    "doi": metadata.get("doi", ""),
                    "cid": metadata.get("cid", item.get("id")),
                    "ipfs_url": metadata.get("ipfs_url", ""),
                    "type": metadata.get("type", "paper"),
                    "parser": metadata.get("parser", ""),
                    "nft_minted": str(metadata.get("nft_minted", "false")).lower() == "true",
                    "created_at": metadata.get("created_at", ""),
                }
            )

        papers.sort(key=lambda paper: paper.get("created_at", ""), reverse=True)
        return papers

    def list_assets(self) -> list[dict[str, Any]]:
        """List locally uploaded asset files."""
        assets = []
        if os.path.exists(self.asset_dir):
            for filename in os.listdir(self.asset_dir):
                if filename.endswith(".pdf") or filename.endswith(".txt"):
                    assets.append({"filename": filename, "path": os.path.join(self.asset_dir, filename)})
        return assets

    def delete_asset(self, asset_id: str):
        """Delete an uploaded asset from vector storage and local disk."""
        self.vector_store.delete_notice(asset_id)

        for filename in os.listdir(self.asset_dir):
            if filename.startswith(asset_id):
                os.remove(os.path.join(self.asset_dir, filename))
                break


_asset_manager = None


def get_asset_manager():
    global _asset_manager
    if _asset_manager is None:
        _asset_manager = AssetManager()
    return _asset_manager
