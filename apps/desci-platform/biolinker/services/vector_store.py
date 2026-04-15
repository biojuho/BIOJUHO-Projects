"""
BioLinker - 벡터 저장소 (Vector Store)
ChromaDB 기반의 RFP 임베딩 저장 및 유사도 검색 기능을 제공합니다.
"""

import hashlib
import itertools
import json
import os
import re
import sys
from datetime import datetime
from typing import Any, cast

import numpy as np  # type: ignore
from dotenv import load_dotenv  # type: ignore

# --- 경로 및 환경 설정 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
# desci-platform/biolinker/services -> desci-platform
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
env_path = os.path.join(project_root, ".env")
load_dotenv(env_path)

# Fallback 환경 변수 로드
if not os.getenv("GOOGLE_API_KEY") and not os.getenv("GEMINI_API_KEY"):
    load_dotenv()

# --- 로컬 모델 임포트 ---
# models.py가 상위 폴더(biolinker)에 위치하므로 sys.path에 추가하여 임포트합니다.
# 서비스가 패키지로 실행되지 않을 경우를 대비한 조치입니다.
BIOLINKER_DIR = os.path.dirname(current_dir)
if BIOLINKER_DIR not in sys.path:
    sys.path.append(BIOLINKER_DIR)

try:
    from models import RFPDocument, VCFirm  # type: ignore
except ImportError:
    # 패키지 컨텍스트에서 실행될 경우 상대 임포트 시도
    try:
        from ..models import RFPDocument, VCFirm  # type: ignore
    except ImportError:
        # 최종 실패 시 로그 출력 및 Any 타입 할당 (크래시 방지)
        print("[경고] models.RFPDocument를 임포트할 수 없습니다. PYTHONPATH를 확인하세요.")
        RFPDocument = Any  # pylint: disable=invalid-name
        VCFirm = Any

# --- 조건부 임포트 (라이브러리 가용성 체크) ---
CHROMADB_AVAILABLE = False  # pylint: disable=invalid-name
try:
    import chromadb  # type: ignore

    # import chromadb.utils.embedding_functions as embedding_functions # 현재 미사용
    CHROMADB_AVAILABLE = True  # pylint: disable=invalid-name
except Exception:  # pylint: disable=broad-exception-caught
    pass


# OpenAI/Google/Qdrant lazy loaders → see embedding_providers.py
from .embedding_providers import (
    OPENAI_AVAILABLE,
    OpenAI,
    GoogleGenerativeAIEmbeddings,
    _load_openai_support,
    _load_google_support,
    _load_qdrant_support,
)




class VectorStore:
    """RFP 공고 벡터 저장소 (ChromaDB + 인메모리 Fallback)"""

    COLLECTION_NAME = "rfp_notices"

    def __init__(self, persist_dir: str = "./chroma_db"):
        self.persist_dir = persist_dir
        self.client = None
        self.collection = None
        self.embedding_fn: Any | None = None
        self.embedding_model = None
        self.openai_client = None

        # 1. Google Embeddings (우선 순위)
        google_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if google_key and _load_google_support():
            # Langchain 임베딩 래퍼
            self.embedding_model = GoogleGenerativeAIEmbeddings(
                model="models/gemini-embedding-001", google_api_key=google_key
            )
            # ChromaDB용 커스텀 함수 래퍼
            self.embedding_fn = self._google_embedding_fn

        # 2. OpenAI Embeddings (대체 수단)
        elif os.getenv("OPENAI_API_KEY") and _load_openai_support():
            self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            self.embedding_fn = self._openai_embedding_fn

        # ChromaDB 초기화
        if CHROMADB_AVAILABLE:
            try:
                # Local variable for type narrowing
                client = chromadb.PersistentClient(path=persist_dir)
                self.client = client
                self.collection = client.get_or_create_collection(
                    name=self.COLLECTION_NAME, metadata={"description": "BioLinker RFP 공고 임베딩"}
                )
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"[오류] ChromaDB 초기화 실패: {e}")
                self.collection = None

    def _google_embedding_fn(self, input_text: Any) -> Any:
        """ChromaDB를 위한 Google Embeddings 래퍼"""
        model = self.embedding_model
        if not model:
            return []
        if isinstance(input_text, str):
            input_text = [input_text]
        return model.embed_documents(input_text)

    def _openai_embedding_fn(self, input_text: Any) -> Any:
        """OpenAI Embeddings 래퍼"""
        if isinstance(input_text, str):
            input_text = [input_text]

        data = []
        client = self.openai_client
        if client:
            for text in input_text:
                response = client.embeddings.create(
                    model="text-embedding-3-small",
                    input=text[:8000],  # type: ignore
                )
                data.append(response.data[0].embedding)
        return data

    def _get_embedding(self, text: str) -> list[float]:
        """단일 텍스트 임베딩 생성"""
        if self.embedding_fn:
            return self.embedding_fn([text])[0]  # type: ignore

        # 임베딩 모델 부재 시 Fallback (개발용)
        if "MOCK_EMBEDDING_WARNING_SHOWN" not in globals():
            print("[중대 경고] 사용 가능한 임베딩 모델이 없습니다! MD5 해시로 대체합니다.")
            print("   -> 의미 기반 검색이 작동하지 않으며 결과는 무작위와 같습니다.")
            globals()["MOCK_EMBEDDING_WARNING_SHOWN"] = True

        hash_val = hashlib.md5(text.encode()).hexdigest()
        # MD5에서 16차원 의사(pseudo) 벡터 생성
        # Linter complaining about string slicing, suppressing error
        return [float(int(hash_val[i : i + 2], 16)) / 255.0 for i in range(0, 32, 2)]  # type: ignore

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        try:
            if value in (None, "", "None"):
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if not value:
            return None
        text = str(value).strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _tokenize_text(text: str) -> set[str]:
        return {token for token in re.findall(r"[0-9A-Za-z가-힣]{2,}", (text or "").lower()) if token}

    @classmethod
    def _backend_filters(cls, filters: dict[str, Any] | None) -> dict[str, Any] | None:
        if not filters:
            return None

        backend_filters = {}
        for key in ("source", "type", "owner_uid"):
            value = filters.get(key)
            if value not in (None, ""):
                backend_filters[key] = value
        return backend_filters or None


    @classmethod
    def _metadata_matches(cls, metadata: dict[str, Any], document: str, filters: dict[str, Any] | None) -> bool:
        if not filters:
            return True

        source_filter = str(filters.get("source", "") or "").strip().lower()
        if source_filter and str(metadata.get("source", "") or "").strip().lower() != source_filter:
            return False

        type_filter = str(filters.get("type", "") or "").strip().lower()
        if type_filter and str(metadata.get("type", "") or "").strip().lower() != type_filter:
            return False

        keyword_filter = str(filters.get("keyword", "") or "").strip().lower()
        if keyword_filter:
            keyword_haystack = " ".join(
                [
                    str(metadata.get("title", "") or ""),
                    str(metadata.get("keywords", "") or ""),
                    str(metadata.get("source", "") or ""),
                    document[:4000],
                ]
            ).lower()
            if keyword_filter not in keyword_haystack:
                return False

        deadline_value = cls._parse_datetime(metadata.get("deadline"))
        deadline_from = cls._parse_datetime(filters.get("deadline_from"))
        deadline_to = cls._parse_datetime(filters.get("deadline_to"))
        if deadline_from and (deadline_value is None or deadline_value < deadline_from):
            return False
        if deadline_to and (deadline_value is None or deadline_value > deadline_to):
            return False

        requested_trl_min = cls._safe_int(filters.get("trl_min"))
        requested_trl_max = cls._safe_int(filters.get("trl_max"))
        item_trl_min = cls._safe_int(metadata.get("min_trl"))
        item_trl_max = cls._safe_int(metadata.get("max_trl"))
        effective_item_min = item_trl_min if item_trl_min is not None else -1
        effective_item_max = item_trl_max if item_trl_max is not None else 99

        if requested_trl_min is not None and effective_item_max < requested_trl_min:
            return False
        if requested_trl_max is not None and effective_item_min > requested_trl_max:
            return False

        return True

    @classmethod
    def _lexical_score(cls, query: str, metadata: dict[str, Any], document: str) -> float:
        query_text = (query or "").strip().lower()
        if not query_text:
            return 0.0

        query_terms = cls._tokenize_text(query_text)
        title_text = str(metadata.get("title", "") or "")
        keyword_text = str(metadata.get("keywords", "") or "")
        source_text = str(metadata.get("source", "") or "")
        combined_text = " ".join([title_text, keyword_text, source_text, document[:4000]])

        if not query_terms:
            return 1.0 if query_text in combined_text.lower() else 0.0

        title_terms = cls._tokenize_text(title_text)
        keyword_terms = cls._tokenize_text(keyword_text)
        source_terms = cls._tokenize_text(source_text)
        all_terms = cls._tokenize_text(combined_text)

        def overlap(term_set: set[str]) -> float:
            return len(query_terms & term_set) / max(len(query_terms), 1)

        exact_bonus = 0.25 if query_text in combined_text.lower() else 0.0
        return min(
            1.0,
            exact_bonus
            + (0.35 * overlap(title_terms))
            + (0.30 * overlap(keyword_terms))
            + (0.25 * overlap(all_terms))
            + (0.10 * overlap(source_terms)),
        )

    @classmethod
    def _post_process_hit_items(
        cls,
        query: str,
        items: list[dict[str, Any]],
        n_results: int,
        filters: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        hybrid_weight = float(os.getenv("HYBRID_SEARCH_TEXT_WEIGHT", "0.2"))
        hybrid_weight = max(0.0, min(1.0, hybrid_weight))

        processed = []
        for item in items:
            metadata = cast(dict[str, Any], item.get("metadata", {}) or {})
            document = str(item.get("document", "") or "")
            if not cls._metadata_matches(metadata, document, filters):
                continue

            vector_score = float(item.get("similarity", 0.0) or 0.0)
            lexical_score = cls._lexical_score(query, metadata, document)
            combined_score = ((1.0 - hybrid_weight) * vector_score) + (hybrid_weight * lexical_score)

            processed.append(
                {
                    **item,
                    "similarity": combined_score,
                    "vector_score": vector_score,
                    "lexical_score": lexical_score,
                }
            )

        processed.sort(
            key=lambda entry: (
                float(entry.get("similarity", 0.0) or 0.0),
                float(entry.get("lexical_score", 0.0) or 0.0),
            ),
            reverse=True,
        )
        return processed[:n_results]

    @classmethod
    def _item_to_document_result(cls, item: dict[str, Any]) -> tuple[RFPDocument, float] | None:
        metadata = cast(dict[str, Any], item.get("metadata", {}) or {})
        try:
            document = RFPDocument(  # type: ignore
                id=str(item.get("id", "")),
                title=str(metadata.get("title", "제목없음")),
                body_text=str(item.get("document", "") or ""),
                source=str(metadata.get("source", "Unknown")),
                deadline=cls._parse_datetime(metadata.get("deadline")),
                keywords=str(metadata.get("keywords", "")).split(",") if metadata.get("keywords") else [],
                url=str(metadata.get("url", "") or "") or None,
                min_trl=cls._safe_int(metadata.get("min_trl")),
                max_trl=cls._safe_int(metadata.get("max_trl")),
            )
            return document, float(item.get("similarity", 0.0) or 0.0)
        except Exception:  # pylint: disable=broad-exception-caught
            return None

    def add_notice(self, rfp: RFPDocument) -> str:
        """RFP 공고 저장"""
        if not rfp.id:
            # ID가 없는 경우 생성 (보통은 있어야 함)
            rfp.id = hashlib.md5(rfp.title.encode()).hexdigest()

        # 임베딩 생성
        embed_text = f"{rfp.title}\n{rfp.body_text[:2000]}"  # type: ignore
        embedding = self._get_embedding(embed_text)

        # 메타데이터 준비
        # Pydantic V2: model_dump 사용 권장
        # ChromaDB 호환성을 위해 단순 타입으로 변환
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

        # Local variable narrowing for self.collection
        collection = self.collection
        if CHROMADB_AVAILABLE and collection:
            # ChromaDB 저장
            collection.add(
                ids=[rfp.id],
                embeddings=[embedding],
                metadatas=[metadata],
                documents=[rfp.body_text[:5000]],  # type: ignore
            )
        else:
            # 단순 인메모리 JSON 저장
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
        """사용자 논문 저장"""
        # 메타데이터 구성 (변수 수 감소를 위해 딕셔너리 바로 생성)
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

        # 임베딩 및 저장
        embed_text = f"{title}\n{abstract}\n{full_text[:3000]}"
        embedding = self._get_embedding(embed_text)

        collection = self.collection
        if CHROMADB_AVAILABLE and collection:
            collection.add(ids=[paper_id], embeddings=[embedding], metadatas=[metadata], documents=[full_text[:5000]])
        else:
            if CHROMADB_AVAILABLE:  # 컬렉션 초기화 실패 케이스
                print("[경고] ChromaDB 컬렉션을 사용할 수 없어 논문 저장을 건너뜁니다.")
            else:
                # 단순 인메모리 JSON 저장 (ChromaDB 미설치)
                self._save_to_json(paper_id, embedding, metadata, full_text[:5000])

        return paper_id

    def add_company_asset(self, asset_id: str, title: str, content: str, metadata: dict[str, Any]) -> str:
        """회사 자산(IR, 특허 등) 저장"""
        # 메타데이터 보강
        final_meta = metadata.copy()
        final_meta.update(
            {
                "title": title,
                "source": metadata.get("source", "CompanyAsset"),
                "type": "company_asset",  # Explicitly set type
                "created_at": datetime.now().isoformat(),
            }
        )

        # 임베딩 생성
        embed_text = f"{title}\n{content[:4000]}"
        embedding = self._get_embedding(embed_text)

        collection = self.collection
        if CHROMADB_AVAILABLE and collection:
            collection.add(ids=[asset_id], embeddings=[embedding], metadatas=[final_meta], documents=[content[:6000]])
        else:
            # 인메모리 저장
            self._save_to_json(asset_id, embedding, final_meta, content[:6000])

        return asset_id

    def add_vc_firm(self, vc: VCFirm) -> str:
        """VC 정보 저장"""
        metadata = {
            "title": vc.name,  # 검색 통일성을 위해 title 필드 사용
            "name": vc.name,
            "source": "VCFirm",
            "type": "vc_firm",
            "country": vc.country,
            "stages": ",".join(vc.preferred_stages),
            "keywords": ",".join(vc.portfolio_keywords),
            "created_at": datetime.now().isoformat(),
        }

        # 임베딩 생성 (Thesis가 가장 중요)
        embed_text = f"{vc.name}\n{vc.investment_thesis}\nKeywords: {', '.join(vc.portfolio_keywords)}"
        embedding = self._get_embedding(embed_text)

        collection = self.collection
        if CHROMADB_AVAILABLE and collection:
            collection.add(ids=[vc.id], embeddings=[embedding], metadatas=[metadata], documents=[vc.investment_thesis])
        else:
            self._save_to_json(vc.id, embedding, metadata, vc.investment_thesis)

        return vc.id

    def add_notices(self, rfps: list[RFPDocument]) -> list[str]:
        """다수의 RFP 공고 저장"""
        ids = []
        for rfp in rfps:
            try:
                doc_id = self.add_notice(rfp)
                ids.append(doc_id)
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"[오류] 공고 저장 실패 {rfp.id}: {e}")
        return ids

    def search_similar(
        self, query: str, n_results: int = 5, filters: dict[str, Any] | None = None
    ) -> list[tuple[RFPDocument, float]]:
        # pylint: disable=too-many-locals
        """유사 공고 검색 (하이브리드 필터 지원)"""
        query_embedding = self._get_embedding(query)
        raw_hits: list[dict[str, Any]] = []
        fetch_limit = max(n_results * 4, n_results)

        collection = self.collection
        if CHROMADB_AVAILABLE and collection:
            try:
                results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=fetch_limit,
                    where=backend_filters,
                    include=["metadatas", "documents", "distances"],
                )

                if results and results.get("ids") and results["ids"][0]:
                    ids = results["ids"][0]

                    def get_result_item(key: str, idx: int, default: Any) -> Any:
                        items = results.get(key)
                        if items and len(items) > 0 and len(items[0]) > idx:
                            return items[0][idx]
                        return default

                    for i, doc_id in enumerate(ids):
                        raw_hits.append(
                            {
                                "id": doc_id,
                                "metadata": get_result_item("metadatas", i, {}) or {},
                                "document": get_result_item("documents", i, "") or "",
                                "similarity": 1.0 - float(get_result_item("distances", i, 0.999)),
                            }
                        )
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"[오류] ChromaDB 검색 실패: {e}")

            if raw_hits:
                processed_hits = self._post_process_hit_items(query, raw_hits, n_results, filters)
                converted_results = []
                for item in processed_hits:
                    converted = self._item_to_document_result(item)
                    if converted:
                        converted_results.append(converted)
                if converted_results:
                    return converted_results

        print("[경고] ChromaDB 검색 실패 또는 미사용, 인메모리 검색을 시도합니다.")
        in_memory_results = self._search_in_memory(query_embedding, fetch_limit, filters)
        processed_hits = self._post_process_hit_items(query, in_memory_results, n_results, filters)

        converted_results = []
        for item in processed_hits:
            converted = self._item_to_document_result(item)
            if converted:
                converted_results.append(converted)
        return converted_results


    def _save_to_json(self, doc_id: str, embedding: list[float], metadata: dict[str, Any], document: str) -> None:
        """인메모리 저장 (JSON Fallback)"""
        db_path = os.path.join(self.persist_dir, "db.json")
        os.makedirs(self.persist_dir, exist_ok=True)

        data: dict[str, Any] = {}
        if os.path.exists(db_path):
            try:
                with open(db_path, encoding="utf-8") as f:
                    data = cast(dict[str, Any], json.load(f))
            except Exception:  # pylint: disable=broad-exception-caught
                pass

        data[doc_id] = {"embedding": embedding, "metadata": metadata, "document": document}

        with open(db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def _search_in_memory(
        self, query_embedding: list[float], n_results: int, filters: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        """인메모리 코사인 유사도 검색"""
        db_path = os.path.join(self.persist_dir, "db.json")
        if not os.path.exists(db_path):
            return []

        data: dict[str, Any] = {}
        try:
            with open(db_path, encoding="utf-8") as f:
                data = cast(dict[str, Any], json.load(f))
        except Exception:  # pylint: disable=broad-exception-caught
            return []

        results = []
        q_vec = np.array(query_embedding)
        q_norm = np.linalg.norm(q_vec)
        post_filters = filters
        filters = None

        for doc_id, item in data.items():
            if not self._metadata_matches(
                cast(dict[str, Any], item.get("metadata", {}) or {}),
                str(item.get("document", "") or ""),
                post_filters,
            ):
                continue
            # 필터 로직
            if filters:
                current_filters: dict[str, Any] = cast(dict[str, Any], filters)
                match = True
                for k, v in current_filters.items():
                    # item is Any, so this access is unchecked but shouldn't error as "undefined base"
                    meta_val = item["metadata"].get(k)
                    # 단순 동등성 체크
                    if meta_val != v:
                        match = False
                        break
                if not match:
                    continue

            d_vec = np.array(item["embedding"])
            d_norm = np.linalg.norm(d_vec)

            if q_norm == 0 or d_norm == 0:
                sim = 0.0
            else:
                sim = float(np.dot(q_vec, d_vec) / (q_norm * d_norm))

            results.append(
                {"id": doc_id, "metadata": item["metadata"], "document": item["document"], "similarity": sim}
            )

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:n_results]  # type: ignore

    def search_by_profile(
        self, tech_keywords: list[str], tech_description: str, n_results: int = 10
    ) -> list[dict[str, Any]]:
        """프로필 기반 검색"""
        query = f"기술 키워드: {', '.join(tech_keywords)}\n역량: {tech_description}"
        results = self.search_similar(query, n_results)

        # 딕셔너리 리스트 반환 (RFPDocument 객체를 dict로 변환)
        return [{**doc.model_dump(), "similarity_score": score} for doc, score in results]

    def get_notice(self, notice_id: str) -> dict[str, Any] | None:
        """ID로 공고 조회"""
        # Local variable narrowing
        collection = self.collection
        if CHROMADB_AVAILABLE and collection:
            try:
                result = collection.get(ids=[notice_id], include=["metadatas", "documents"])
                if result["ids"]:
                    return {
                        "id": notice_id,
                        "metadata": result["metadatas"][0],  # type: ignore
                        "document": result["documents"][0],  # type: ignore
                    }
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        else:
            # JSON 확인
            db_path = os.path.join(self.persist_dir, "db.json")
            if os.path.exists(db_path):
                try:
                    with open(db_path, encoding="utf-8") as f:
                        data = json.load(f)
                        if notice_id in data:
                            return {
                                "id": notice_id,
                                "metadata": data[notice_id]["metadata"],
                                "document": data[notice_id]["document"],
                            }
                except Exception:  # pylint: disable=broad-exception-caught
                    pass
        return None

    def delete_notice(self, notice_id: str) -> None:
        """ID로 공고 삭제"""
        # Local variable narrowing
        collection = self.collection
        if CHROMADB_AVAILABLE and collection:
            try:
                collection.delete(ids=[notice_id])
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"[오류] 공고 삭제 실패 {notice_id}: {e}")
        else:
            db_path = os.path.join(self.persist_dir, "db.json")
            if os.path.exists(db_path):
                try:
                    with open(db_path, encoding="utf-8") as f:
                        data = json.load(f)
                    if notice_id in data:
                        del data[notice_id]
                        with open(db_path, "w", encoding="utf-8") as f:
                            json.dump(data, f, ensure_ascii=False)
                except Exception:  # pylint: disable=broad-exception-caught
                    pass

    def count(self) -> int:
        """총 공고 수 조회"""
        # Local variable narrowing
        collection = self.collection
        if CHROMADB_AVAILABLE and collection:
            return collection.count()

        # 인메모리 카운트
        db_path = os.path.join(self.persist_dir, "db.json")
        if os.path.exists(db_path):
            try:
                with open(db_path, encoding="utf-8") as f:
                    data = json.load(f)
                    return len(data)
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        return 0

    def list_all(self, limit: int = 100) -> list[dict[str, Any]]:
        """모든 공고 목록 조회 (메타데이터 포함)"""
        # Local variable narrowing
        collection = self.collection
        if CHROMADB_AVAILABLE and collection:
            try:
                result = collection.get(limit=limit, include=["metadatas"])
                ids = result.get("ids", []) or []
                metadatas = result.get("metadatas", []) or []

                items = []
                for i, id_ in enumerate(ids):
                    # 범위 체크 및 None 체크
                    meta = metadatas[i] if (i < len(metadatas) and metadatas[i]) else {}  # type: ignore
                    items.append({"id": id_, "metadata": meta})
                return items
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"[오류] ChromaDB 전체 목록 조회 실패: {e}")
                return []

        # ChromaDB 미사용 시 인메모리 JSON fallback
        db_path = os.path.join(self.persist_dir, "db.json")
        if os.path.exists(db_path):
            try:
                with open(db_path, encoding="utf-8") as f:
                    data = json.load(f)
                return [{"id": k, "metadata": v["metadata"]} for k, v in itertools.islice(data.items(), limit)]
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        return []

    def get_documents_by_metadata(self, key: str, value: Any) -> list[dict[str, Any]]:
        """메타데이터 키-값으로 문서 조회"""
        collection = self.collection
        if CHROMADB_AVAILABLE and collection:
            try:
                result = collection.get(where={key: value}, include=["metadatas", "documents"])
                items = []
                ids = result.get("ids", []) or []
                metadatas = result.get("metadatas", []) or []
                documents = result.get("documents", []) or []

                for i, id_ in enumerate(ids):
                    items.append({"id": id_, "metadata": metadatas[i], "document": documents[i]})
                return items
            except Exception as e:
                print(f"[오류] ChromaDB 메타데이터 조회 실패: {e}")
                return []

        # In-memory fallback
        db_path = os.path.join(self.persist_dir, "db.json")
        items = []
        if os.path.exists(db_path):
            try:
                with open(db_path, encoding="utf-8") as f:
                    data = json.load(f)
                    for doc_id, val in data.items():
                        if val.get("metadata", {}).get(key) == value:
                            items.append({"id": doc_id, "metadata": val["metadata"], "document": val["document"]})
            except Exception:
                pass
        return items


# ── QdrantVectorStore (extracted to qdrant_store.py) ──
from .qdrant_store import QdrantVectorStore  # noqa: E402,F401



_VECTOR_STORE: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """VectorStore 싱글톤 인스턴스 반환"""
    global _VECTOR_STORE  # pylint: disable=global-statement
    if _VECTOR_STORE is None:
        backend = os.getenv("VECTOR_STORE_BACKEND", "chroma").strip().lower()
        if backend == "qdrant":
            if _load_qdrant_support():
                try:
                    _VECTOR_STORE = QdrantVectorStore()
                except Exception as e:  # pylint: disable=broad-exception-caught
                    print(f"[경고] Qdrant 초기화 실패, ChromaDB fallback 사용: {e}")
                    _VECTOR_STORE = VectorStore()
            else:
                print("[경고] qdrant-client 미설치 상태입니다. ChromaDB fallback 사용")
                _VECTOR_STORE = VectorStore()
        else:
            _VECTOR_STORE = VectorStore()
    return _VECTOR_STORE

