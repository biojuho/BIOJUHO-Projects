"""
BioLinker - Vector Store
ChromaDB 기반 공고 임베딩 저장 및 유사도 검색
"""
import os
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import RFPDocument

# ChromaDB & OpenAI imports
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class VectorStore:
    """공고 벡터 저장소 (ChromaDB)"""
    
    COLLECTION_NAME = "rfp_notices"
    EMBEDDING_MODEL = "text-embedding-3-small"
    
    def __init__(self, persist_dir: str = "./chroma_db"):
        self.persist_dir = persist_dir
        self.client = None
        self.collection = None
        self.openai_client = None
        
        # OpenAI 클라이언트 초기화
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key and OPENAI_AVAILABLE:
            self.openai_client = OpenAI(api_key=api_key)
        
        # ChromaDB 초기화
        if CHROMADB_AVAILABLE:
            self.client = chromadb.PersistentClient(path=persist_dir)
            self.collection = self.client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"description": "BioLinker RFP Notice Embeddings"}
            )
    
    def _get_embedding(self, text: str) -> list[float]:
        """OpenAI 임베딩 생성"""
        if not self.openai_client:
            # OpenAI 없으면 간단한 해시 기반 임베딩 (테스트용)
            import hashlib
            hash_val = hashlib.md5(text.encode()).hexdigest()
            return [float(int(hash_val[i:i+2], 16)) / 255 for i in range(0, 32, 2)]
        
        response = self.openai_client.embeddings.create(
            model=self.EMBEDDING_MODEL,
            input=text[:8000]  # 토큰 제한
        )
        return response.data[0].embedding
    
    def add_notice(self, rfp: RFPDocument) -> str:
        """공고 저장"""
        if not CHROMADB_AVAILABLE or not self.collection:
            raise RuntimeError("ChromaDB가 설치되어 있지 않습니다")
        
        # 임베딩 생성
        embed_text = f"{rfp.title}\n{rfp.body_text[:2000]}"
        embedding = self._get_embedding(embed_text)
        
        # 메타데이터
        metadata = {
            "title": rfp.title,
            "source": rfp.source,
            "url": rfp.url or "",
            "keywords": ",".join(rfp.keywords),
            "deadline": rfp.deadline.isoformat() if rfp.deadline else "",
            "created_at": datetime.now().isoformat()
        }
        
        # 저장
        self.collection.add(
            ids=[rfp.id],
            embeddings=[embedding],
            metadatas=[metadata],
            documents=[rfp.body_text[:5000]]
        )
        
        return rfp.id
    
    def add_notices(self, rfps: list[RFPDocument]) -> list[str]:
        """여러 공고 일괄 저장"""
        ids = []
        for rfp in rfps:
            try:
                doc_id = self.add_notice(rfp)
                ids.append(doc_id)
            except Exception as e:
                print(f"Error adding notice {rfp.id}: {e}")
        return ids
    
    def search_similar(
        self, 
        query: str, 
        n_results: int = 5,
        source_filter: Optional[str] = None
    ) -> list[dict]:
        """유사 공고 검색"""
        if not CHROMADB_AVAILABLE or not self.collection:
            return []
        
        # 쿼리 임베딩
        query_embedding = self._get_embedding(query)
        
        # 필터 조건
        where = None
        if source_filter:
            where = {"source": source_filter}
        
        # 검색
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=["metadatas", "documents", "distances"]
        )
        
        # 결과 포맷
        notices = []
        for i, doc_id in enumerate(results['ids'][0]):
            notices.append({
                'id': doc_id,
                'metadata': results['metadatas'][0][i],
                'document': results['documents'][0][i][:500],
                'similarity': 1 - results['distances'][0][i]  # distance to similarity
            })
        
        return notices
    
    def search_by_profile(
        self,
        tech_keywords: list[str],
        tech_description: str,
        n_results: int = 10
    ) -> list[dict]:
        """사용자 프로필 기반 공고 추천"""
        query = f"기술 키워드: {', '.join(tech_keywords)}\n역량: {tech_description}"
        return self.search_similar(query, n_results)
    
    def get_notice(self, notice_id: str) -> Optional[dict]:
        """ID로 공고 조회"""
        if not CHROMADB_AVAILABLE or not self.collection:
            return None
        
        try:
            result = self.collection.get(
                ids=[notice_id],
                include=["metadatas", "documents"]
            )
            if result['ids']:
                return {
                    'id': notice_id,
                    'metadata': result['metadatas'][0],
                    'document': result['documents'][0]
                }
        except Exception:
            pass
        return None
    
    def delete_notice(self, notice_id: str):
        """공고 삭제"""
        if self.collection:
            self.collection.delete(ids=[notice_id])
    
    def count(self) -> int:
        """저장된 공고 수"""
        if self.collection:
            return self.collection.count()
        return 0
    
    def list_all(self, limit: int = 100) -> list[dict]:
        """모든 공고 목록"""
        if not self.collection:
            return []
        
        result = self.collection.get(
            limit=limit,
            include=["metadatas"]
        )
        
        return [
            {'id': id_, 'metadata': meta}
            for id_, meta in zip(result['ids'], result['metadatas'])
        ]


# Singleton
_vector_store: Optional[VectorStore] = None

def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
