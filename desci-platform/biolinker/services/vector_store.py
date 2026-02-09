"""
BioLinker - 벡터 저장소 (Vector Store)
ChromaDB 기반의 RFP 임베딩 저장 및 유사도 검색 기능을 제공합니다.
"""
import os
import sys
import json
import hashlib
import itertools
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, cast

import numpy as np # type: ignore
from dotenv import load_dotenv # type: ignore

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
    from models import RFPDocument # type: ignore
except ImportError:
    # 패키지 컨텍스트에서 실행될 경우 상대 임포트 시도
    try:
        from ..models import RFPDocument # type: ignore
    except ImportError:
        # 최종 실패 시 로그 출력 및 Any 타입 할당 (크래시 방지)
        print("[경고] models.RFPDocument를 임포트할 수 없습니다. PYTHONPATH를 확인하세요.")
        RFPDocument = Any  # pylint: disable=invalid-name

# --- 조건부 임포트 (라이브러리 가용성 체크) ---
CHROMADB_AVAILABLE = False  # pylint: disable=invalid-name
try:
    import chromadb # type: ignore
    # import chromadb.utils.embedding_functions as embedding_functions # 현재 미사용
    CHROMADB_AVAILABLE = True  # pylint: disable=invalid-name
except Exception:  # pylint: disable=broad-exception-caught
    pass

OPENAI_AVAILABLE = False  # pylint: disable=invalid-name
try:
    from openai import OpenAI # type: ignore
    OPENAI_AVAILABLE = True  # pylint: disable=invalid-name
except Exception:  # pylint: disable=broad-exception-caught
    pass

_GOOGLE_AVAILABLE = False  # pylint: disable=invalid-name
try:
    from langchain_google_genai import GoogleGenerativeAIEmbeddings # type: ignore
    _GOOGLE_AVAILABLE = True  # pylint: disable=invalid-name
except Exception:  # pylint: disable=broad-exception-caught
    pass


class VectorStore:
    """RFP 공고 벡터 저장소 (ChromaDB + 인메모리 Fallback)"""

    COLLECTION_NAME = "rfp_notices"

    def __init__(self, persist_dir: str = "./chroma_db"):
        self.persist_dir = persist_dir
        self.client = None
        self.collection = None
        self.embedding_fn: Optional[Any] = None
        self.embedding_model = None
        self.openai_client = None

        # 1. Google Embeddings (우선 순위)
        google_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if google_key and _GOOGLE_AVAILABLE:
            # Langchain 임베딩 래퍼
            self.embedding_model = GoogleGenerativeAIEmbeddings(
                model="models/gemini-embedding-001",
                google_api_key=google_key
            )
            # ChromaDB용 커스텀 함수 래퍼
            self.embedding_fn = self._google_embedding_fn

        # 2. OpenAI Embeddings (대체 수단)
        elif os.getenv("OPENAI_API_KEY") and OPENAI_AVAILABLE:
            self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            self.embedding_fn = self._openai_embedding_fn

        # ChromaDB 초기화
        if CHROMADB_AVAILABLE:
            try:
                # Local variable for type narrowing
                client = chromadb.PersistentClient(path=persist_dir)
                self.client = client
                self.collection = client.get_or_create_collection(
                    name=self.COLLECTION_NAME,
                    metadata={"description": "BioLinker RFP 공고 임베딩"}
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
                    input=text[:8000] # type: ignore
                )
                data.append(response.data[0].embedding)
        return data

    def _get_embedding(self, text: str) -> List[float]:
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
        return [float(int(hash_val[i : i + 2], 16)) / 255.0 for i in range(0, 32, 2)] # type: ignore

    def add_notice(self, rfp: RFPDocument) -> str:
        """RFP 공고 저장"""
        if not rfp.id:
            # ID가 없는 경우 생성 (보통은 있어야 함)
            rfp.id = hashlib.md5(rfp.title.encode()).hexdigest()

        # 임베딩 생성
        embed_text = f"{rfp.title}\n{rfp.body_text[:2000]}" # type: ignore
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
            "created_at": datetime.now().isoformat()
        }

        # Local variable narrowing for self.collection
        collection = self.collection
        if CHROMADB_AVAILABLE and collection:
            # ChromaDB 저장
            collection.add(
                ids=[rfp.id],
                embeddings=[embedding],
                metadatas=[metadata],
                documents=[rfp.body_text[:5000]] # type: ignore
            )
        else:
            # 단순 인메모리 JSON 저장
            self._save_to_json(rfp.id, embedding, metadata, rfp.body_text[:5000]) # type: ignore

        return rfp.id

    def add_paper(  # pylint: disable=too-many-arguments, too-many-locals
        self, paper_id: str, title: str, abstract: str, full_text: str, keywords: List[str]
    ) -> str:
        """사용자 논문 저장"""
        # 메타데이터 구성 (변수 수 감소를 위해 딕셔너리 바로 생성)
        metadata = {
            "title": title,
            "source": "Paper",
            "type": "paper",
            "keywords": ",".join(keywords),
            "created_at": datetime.now().isoformat()
        }

        # 임베딩 및 저장
        embed_text = f"{title}\n{abstract}\n{full_text[:3000]}"
        embedding = self._get_embedding(embed_text)

        collection = self.collection
        if CHROMADB_AVAILABLE and collection:
            collection.add(
                ids=[paper_id],
                embeddings=[embedding],
                metadatas=[metadata],
                documents=[full_text[:5000]]
            )
        else:
            if CHROMADB_AVAILABLE: # 컬렉션 초기화 실패 케이스
                print("[경고] ChromaDB 컬렉션을 사용할 수 없어 논문 저장을 건너뜁니다.")
            else:
                # 단순 인메모리 JSON 저장 (ChromaDB 미설치)
                self._save_to_json(paper_id, embedding, metadata, full_text[:5000])

        return paper_id

    def add_notices(self, rfps: List[RFPDocument]) -> List[str]:
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
        self,
        query: str,
        n_results: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[RFPDocument, float]]:
        # pylint: disable=too-many-locals
        """유사 공고 검색 (하이브리드 필터 지원)"""
        query_embedding = self._get_embedding(query)
        found_docs: List[Tuple[RFPDocument, float]] = []

        # Local variable narrowing
        collection = self.collection
        if CHROMADB_AVAILABLE and collection:
            # ChromaDB 검색
            try:
                results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    where=filters, # filters가 None이면 where절 생략됨
                    include=["metadatas", "documents", "distances"]
                )

                # 결과가 존재하고 비어있지 않은지 확인
                if results and results.get('ids') and results['ids'][0]:
                    ids = results['ids'][0]
                    # 안전한 리스트 접근을 위한 헬퍼 함수
                    def get_result_item(key: str, idx: int, default: Any) -> Any:
                        items = results.get(key)
                        if items and len(items) > 0 and len(items[0]) > idx:
                            return items[0][idx]
                        return default

                    for i, doc_id in enumerate(ids):
                        doc_text = get_result_item('documents', i, "")
                        raw_meta = get_result_item('metadatas', i, {})
                        dist = get_result_item('distances', i, 0.999) # 기본값: 매우 먼 거리

                        # 엄격한 타입 검사를 위한 변환
                        meta: Dict[str, Any] = raw_meta if isinstance(raw_meta, dict) else {}

                        # RFPDocument 재구성
                        try:
                            doc = RFPDocument( # type: ignore
                                id=doc_id,
                                title=str(meta.get("title", "알 수 없음")),
                                body_text=doc_text,
                                source=str(meta.get("source", "알 수 없음")),
                                deadline=None,  # 필요시 파싱, 단순 검색에서는 생략
                                keywords=str(meta.get("keywords", "")).split(",") if meta.get("keywords") else []
                            )
                            # Chroma는 거리(distance) 반환 (낮을수록 좋음), 유사도(1 - dist)로 변환
                            found_docs.append((doc, 1.0 - float(dist)))
                        except Exception: # pylint: disable=broad-exception-caught
                            continue

            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"[오류] ChromaDB 검색 실패: {e}") 
                # 여기서 에러 발생 시 인메모리 검색으로 넘어감

            # ChromaDB 결과가 있으면 반환 (인메모리 검색 생략)
            if found_docs:
                return found_docs

        print("[경고] ChromaDB 검색 실패 또는 미사용. 인메모리 검색을 시도합니다.")
        # 단순 인메모리 검색
        in_memory_results = self._search_in_memory(query_embedding, n_results, filters)

        converted_results = []
        for item in in_memory_results:
            meta = item['metadata']
            try:
                doc = RFPDocument( # type: ignore
                    id=item['id'],
                    title=str(meta.get("title", "알 수 없음")),
                    body_text=item['document'],
                    source=str(meta.get("source", "알 수 없음")),
                    deadline=None,
                    keywords=str(meta.get("keywords", "")).split(",") if meta.get("keywords") else []
                )
                converted_results.append((doc, item['similarity']))
            except Exception: # pylint: disable=broad-exception-caught
                continue
        return converted_results

    def _save_to_json(
        self, doc_id: str, embedding: List[float], metadata: Dict[str, Any], document: str
    ) -> None:
        """인메모리 저장 (JSON Fallback)"""
        db_path = os.path.join(self.persist_dir, "db.json")
        os.makedirs(self.persist_dir, exist_ok=True)

        data: Dict[str, Any] = {}
        if os.path.exists(db_path):
            try:
                with open(db_path, 'r', encoding='utf-8') as f:
                    data = cast(Dict[str, Any], json.load(f))
            except Exception:  # pylint: disable=broad-exception-caught
                pass

        data[doc_id] = {
            "embedding": embedding,
            "metadata": metadata,
            "document": document
        }

        with open(db_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)

    def _search_in_memory(
        self, query_embedding: List[float], n_results: int, filters: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """인메모리 코사인 유사도 검색"""
        db_path = os.path.join(self.persist_dir, "db.json")
        if not os.path.exists(db_path):
            return []

        data: Dict[str, Any] = {}
        try:
            with open(db_path, 'r', encoding='utf-8') as f:
                data = cast(Dict[str, Any], json.load(f))
        except Exception:  # pylint: disable=broad-exception-caught
            return []

        results = []
        q_vec = np.array(query_embedding)
        q_norm = np.linalg.norm(q_vec)

        for doc_id, item in data.items():
            # 필터 로직
            if filters:
                current_filters: Dict[str, Any] = cast(Dict[str, Any], filters)
                match = True
                for k, v in current_filters.items():
                    # item is Any, so this access is unchecked but shouldn't error as "undefined base"
                    meta_val = item['metadata'].get(k)
                    # 단순 동등성 체크
                    if meta_val != v:
                        match = False
                        break
                if not match:
                    continue

            d_vec = np.array(item['embedding'])
            d_norm = np.linalg.norm(d_vec)

            if q_norm == 0 or d_norm == 0:
                sim = 0.0
            else:
                sim = float(np.dot(q_vec, d_vec) / (q_norm * d_norm))

            results.append({
                'id': doc_id,
                'metadata': item['metadata'],
                'document': item['document'],
                'similarity': sim
            })

        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:n_results] # type: ignore

    def search_by_profile(
        self,
        tech_keywords: List[str],
        tech_description: str,
        n_results: int = 10
    ) -> List[Dict[str, Any]]:
        """프로필 기반 검색"""
        query = f"기술 키워드: {', '.join(tech_keywords)}\n역량: {tech_description}"
        results = self.search_similar(query, n_results)

        # 딕셔너리 리스트 반환 (RFPDocument 객체를 dict로 변환)
        return [
            {**doc.model_dump(), "similarity_score": score}
            for doc, score in results
        ]

    def get_notice(self, notice_id: str) -> Optional[Dict[str, Any]]:
        """ID로 공고 조회"""
        # Local variable narrowing
        collection = self.collection
        if CHROMADB_AVAILABLE and collection:
            try:
                result = collection.get(ids=[notice_id], include=["metadatas", "documents"])
                if result['ids']:
                    return {
                        'id': notice_id,
                        'metadata': result['metadatas'][0], # type: ignore
                        'document': result['documents'][0] # type: ignore
                    }
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        else:
            # JSON 확인
            db_path = os.path.join(self.persist_dir, "db.json")
            if os.path.exists(db_path):
                try:
                    with open(db_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if notice_id in data:
                            return {
                                'id': notice_id,
                                'metadata': data[notice_id]['metadata'],
                                'document': data[notice_id]['document']
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
                    with open(db_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if notice_id in data:
                        del data[notice_id]
                        with open(db_path, 'w', encoding='utf-8') as f:
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
                with open(db_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return len(data)
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        return 0

    def list_all(self, limit: int = 100) -> List[Dict[str, Any]]:
        """모든 공고 목록 조회 (메타데이터 포함)"""
        # Local variable narrowing
        collection = self.collection
        if CHROMADB_AVAILABLE and collection:
            try:
                result = collection.get(limit=limit, include=["metadatas"])
                ids = result.get('ids', []) or []
                metadatas = result.get('metadatas', []) or []

                items = []
                for i, id_ in enumerate(ids):
                    # 범위 체크 및 None 체크
                    meta = metadatas[i] if (i < len(metadatas) and metadatas[i]) else {} # type: ignore
                    items.append({'id': id_, 'metadata': meta})
                return items
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"[오류] ChromaDB 전체 목록 조회 실패: {e}")
                return []
        else:
            db_path = os.path.join(self.persist_dir, "db.json")
            if os.path.exists(db_path):
                try:
                    with open(db_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    # list slicing 대신 islice 사용 (Linter 호환성)
                    return [{'id': k, 'metadata': v['metadata']} for k, v in itertools.islice(data.items(), limit)]
                except Exception:  # pylint: disable=broad-exception-caught
                    pass
            return []


# 싱글톤 패턴 (Singleton Pattern)
_VECTOR_STORE: Optional[VectorStore] = None

def get_vector_store() -> VectorStore:
    """VectorStore 싱글톤 인스턴스 반환"""
    global _VECTOR_STORE  # pylint: disable=global-statement
    if _VECTOR_STORE is None:
        _VECTOR_STORE = VectorStore()
    return _VECTOR_STORE
