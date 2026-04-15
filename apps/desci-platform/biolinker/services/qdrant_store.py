"""
BioLinker — Qdrant Vector Store Adapter

QdrantVectorStore extends VectorStore with Qdrant-backed persistence.
Extracted from vector_store.py to enforce single-responsibility.
"""

import hashlib
import os
from datetime import datetime
from typing import Any

from .embedding_providers import (
    QDRANT_AVAILABLE,
    QdrantClient,
    _load_qdrant_support,
    init_embedding_fn,
    qdrant_models,
)
from .vector_store import VectorStore

try:
    from models import RFPDocument, VCFirm  # type: ignore
except ImportError:
    try:
        from ..models import RFPDocument, VCFirm  # type: ignore
    except ImportError:
        RFPDocument = Any  # type: ignore  # pylint: disable=invalid-name
        VCFirm = Any


class QdrantVectorStore(VectorStore):
    """Qdrant-backed vector store adapter with the same public API."""

    def __init__(self, persist_dir: str = "./chroma_db"):
        self.persist_dir = persist_dir
        self.client = None
        self.collection = None

        init_embedding_fn(self)

        if not _load_qdrant_support() or QdrantClient is None:
            raise RuntimeError("qdrant-client is not installed")

        self.collection_name = os.getenv("QDRANT_COLLECTION_NAME", self.COLLECTION_NAME)
        self.qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        self.qdrant_api_key = os.getenv("QDRANT_API_KEY")
        self.qdrant_timeout = float(os.getenv("QDRANT_TIMEOUT_SECONDS", "10"))
        self._collection_ready = False
        self.qdrant_client = QdrantClient(
            url=self.qdrant_url,
            api_key=self.qdrant_api_key or None,
            timeout=self.qdrant_timeout,
        )

    def _ensure_collection(self, vector_size: int) -> None:
        if self._collection_ready:
            return

        try:
            self.qdrant_client.get_collection(self.collection_name)
            self._collection_ready = True
            return
        except Exception:  # pylint: disable=broad-exception-caught
            pass

        if qdrant_models is None:
            raise RuntimeError("qdrant models are unavailable")

        self.qdrant_client.create_collection(
            collection_name=self.collection_name,
            vectors_config=qdrant_models.VectorParams(
                size=vector_size,
                distance=qdrant_models.Distance.COSINE,
            ),
        )
        self._collection_ready = True

    @staticmethod
    def _build_filter(filters: dict[str, Any] | None) -> Any:
        backend_filters = VectorStore._backend_filters(filters)
        if not backend_filters or qdrant_models is None:
            return None

        must_conditions = [
            qdrant_models.FieldCondition(
                key=str(key),
                match=qdrant_models.MatchValue(value=value),
            )
            for key, value in backend_filters.items()
        ]
        return qdrant_models.Filter(must=must_conditions)

    def _upsert_payload(
        self,
        doc_id: str,
        embedding: list[float],
        metadata: dict[str, Any],
        document: str,
    ) -> None:
        self._ensure_collection(len(embedding))
        payload = metadata.copy()
        payload["document"] = document
        if qdrant_models is None:
            raise RuntimeError("qdrant models are unavailable")

        self.qdrant_client.upsert(
            collection_name=self.collection_name,
            wait=True,
            points=[
                qdrant_models.PointStruct(
                    id=doc_id,
                    vector=embedding,
                    payload=payload,
                )
            ],
        )

    # ── CRUD overrides ─────────────────────────────────

    def add_notice(self, rfp: RFPDocument) -> str:
        if not rfp.id:
            rfp.id = hashlib.md5(rfp.title.encode()).hexdigest()

        embed_text = f"{rfp.title}\n{rfp.body_text[:2000]}"  # type: ignore
        embedding = self._get_embedding(embed_text)
        metadata = {
            "title": rfp.title,
            "source": rfp.source,
            "url": rfp.url or "",
            "keywords": ",".join(rfp.keywords),
            "deadline": rfp.deadline.isoformat() if rfp.deadline else "",
            "budget": rfp.budget_range or "",
            "min_trl": rfp.min_trl if rfp.min_trl is not None else -1,
            "max_trl": rfp.max_trl if rfp.max_trl is not None else 99,
            "created_at": datetime.now().isoformat(),
        }

        try:
            self._upsert_payload(rfp.id, embedding, metadata, rfp.body_text[:5000])  # type: ignore
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"[오류] Qdrant 저장 실패, JSON fallback 사용: {e}")
            self._save_to_json(rfp.id, embedding, metadata, rfp.body_text[:5000])  # type: ignore

        return rfp.id

    def add_paper(  # pylint: disable=too-many-arguments, too-many-locals
        self,
        paper_id: str,
        title: str,
        abstract: str,
        full_text: str,
        keywords: list[str],
        authors: list[str] | None = None,
        affiliations: list[str] | None = None,
        references: list[str] | None = None,
        doi: str | None = None,
        parser: str | None = None,
        owner_uid: str | None = None,
        owner_email: str | None = None,
        owner_name: str | None = None,
        cid: str | None = None,
        ipfs_url: str | None = None,
        created_at: str | None = None,
        nft_minted: bool = False,
    ) -> str:
        reference_items = [reference for reference in (references or []) if reference]
        metadata = {
            "title": title,
            "abstract": abstract,
            "source": "Paper",
            "type": "paper",
            "keywords": ",".join(keywords),
            "authors": ", ".join(authors or []),
            "affiliations": " | ".join(affiliations or []),
            "references": " || ".join(reference_items[:25]),
            "reference_count": len(reference_items),
            "doi": doi or "",
            "parser": parser or "",
            "owner_uid": owner_uid or "",
            "owner_email": owner_email or "",
            "owner_name": owner_name or "",
            "cid": cid or paper_id,
            "ipfs_url": ipfs_url or "",
            "nft_minted": str(nft_minted).lower(),
            "created_at": created_at or datetime.now().isoformat(),
        }
        embed_text = f"{title}\n{abstract}\n{full_text[:3000]}"
        embedding = self._get_embedding(embed_text)

        try:
            self._upsert_payload(paper_id, embedding, metadata, full_text[:5000])
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"[오류] Qdrant 논문 저장 실패, JSON fallback 사용: {e}")
            self._save_to_json(paper_id, embedding, metadata, full_text[:5000])

        return paper_id

    def add_company_asset(self, asset_id: str, title: str, content: str, metadata: dict[str, Any]) -> str:
        final_meta = metadata.copy()
        final_meta.update(
            {
                "title": title,
                "source": metadata.get("source", "CompanyAsset"),
                "type": "company_asset",
                "created_at": datetime.now().isoformat(),
            }
        )
        embed_text = f"{title}\n{content[:4000]}"
        embedding = self._get_embedding(embed_text)

        try:
            self._upsert_payload(asset_id, embedding, final_meta, content[:6000])
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"[오류] Qdrant 자산 저장 실패, JSON fallback 사용: {e}")
            self._save_to_json(asset_id, embedding, final_meta, content[:6000])

        return asset_id

    def add_vc_firm(self, vc: VCFirm) -> str:
        metadata = {
            "title": vc.name,
            "name": vc.name,
            "source": "VCFirm",
            "type": "vc_firm",
            "country": vc.country,
            "stages": ",".join(vc.preferred_stages),
            "keywords": ",".join(vc.portfolio_keywords),
            "created_at": datetime.now().isoformat(),
        }
        embed_text = f"{vc.name}\n{vc.investment_thesis}\nKeywords: {', '.join(vc.portfolio_keywords)}"
        embedding = self._get_embedding(embed_text)

        try:
            self._upsert_payload(vc.id, embedding, metadata, vc.investment_thesis)
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"[오류] Qdrant VC 저장 실패, JSON fallback 사용: {e}")
            self._save_to_json(vc.id, embedding, metadata, vc.investment_thesis)

        return vc.id

    # ── Search override ────────────────────────────────

    def search_similar(
        self, query: str, n_results: int = 5, filters: dict[str, Any] | None = None
    ) -> list[tuple[RFPDocument, float]]:
        query_embedding = self._get_embedding(query)
        raw_hits: list[dict[str, Any]] = []
        fetch_limit = max(n_results * 4, n_results)

        try:
            results = self.qdrant_client.query_points(
                collection_name=self.collection_name,
                query=query_embedding,
                query_filter=self._build_filter(filters),
                with_payload=True,
                limit=fetch_limit,
            ).points

            for point in results:
                payload = dict(getattr(point, "payload", {}) or {})
                raw_hits.append(
                    {
                        "id": str(getattr(point, "id", "")),
                        "metadata": {k: v for k, v in payload.items() if k != "document"},
                        "document": str(payload.get("document", "") or ""),
                        "similarity": float(getattr(point, "score", 0.0) or 0.0),
                    }
                )
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"[오류] Qdrant 검색 실패: {e}")

        if raw_hits:
            processed_hits = self._post_process_hit_items(query, raw_hits, n_results, filters)
            converted_results = []
            for item in processed_hits:
                converted = self._item_to_document_result(item)
                if converted:
                    converted_results.append(converted)
            if converted_results:
                return converted_results

        print("[경고] Qdrant 검색 실패 또는 미사용, 인메모리 검색을 시도합니다.")
        in_memory_results = self._search_in_memory(query_embedding, fetch_limit, filters)
        processed_hits = self._post_process_hit_items(query, in_memory_results, n_results, filters)
        converted_results = []
        for item in processed_hits:
            converted = self._item_to_document_result(item)
            if converted:
                converted_results.append(converted)
        return converted_results

    # ── Read / Delete overrides ────────────────────────

    def get_notice(self, notice_id: str) -> dict[str, Any] | None:
        try:
            results = self.qdrant_client.retrieve(
                collection_name=self.collection_name,
                ids=[notice_id],
                with_payload=True,
                with_vectors=False,
            )
            if results:
                point = results[0]
                payload = dict(getattr(point, "payload", {}) or {})
                document = str(payload.pop("document", "") or "")
                return {
                    "id": str(getattr(point, "id", notice_id)),
                    "metadata": payload,
                    "document": document,
                }
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        return super().get_notice(notice_id)

    def delete_notice(self, notice_id: str) -> None:
        try:
            if qdrant_models is not None:
                self.qdrant_client.delete(
                    collection_name=self.collection_name,
                    points_selector=qdrant_models.PointIdsList(points=[notice_id]),
                    wait=True,
                )
                return
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"[오류] Qdrant 삭제 실패 {notice_id}: {e}")
        super().delete_notice(notice_id)

    def count(self) -> int:
        try:
            result = self.qdrant_client.count(
                collection_name=self.collection_name,
                exact=True,
            )
            return int(getattr(result, "count", 0) or 0)
        except Exception:  # pylint: disable=broad-exception-caught
            return super().count()

    def list_all(self, limit: int = 100) -> list[dict[str, Any]]:
        try:
            records, _ = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
            items = []
            for point in records:
                payload = dict(getattr(point, "payload", {}) or {})
                payload.pop("document", None)
                items.append({"id": str(getattr(point, "id", "")), "metadata": payload})
            return items
        except Exception:  # pylint: disable=broad-exception-caught
            return super().list_all(limit)

    def get_documents_by_metadata(self, key: str, value: Any) -> list[dict[str, Any]]:
        try:
            records, _ = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                scroll_filter=self._build_filter({key: value}),
                limit=100,
                with_payload=True,
                with_vectors=False,
            )
            items = []
            for point in records:
                payload = dict(getattr(point, "payload", {}) or {})
                document = str(payload.pop("document", "") or "")
                items.append(
                    {
                        "id": str(getattr(point, "id", "")),
                        "metadata": payload,
                        "document": document,
                    }
                )
            return items
        except Exception:  # pylint: disable=broad-exception-caught
            return super().get_documents_by_metadata(key, value)
