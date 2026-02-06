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

# ChromaDB, OpenAI, Google imports
try:
    import chromadb
    import chromadb.utils.embedding_functions as embedding_functions
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False


class VectorStore:
    """공고 벡터 저장소 (ChromaDB)"""
    
    COLLECTION_NAME = "rfp_notices"
    
    def __init__(self, persist_dir: str = "./chroma_db"):
        self.persist_dir = persist_dir
        self.client = None
        self.collection = None
        self.embedding_fn = None
        
        # 1. Google Embeddings (Priority)
        google_key = os.getenv("GOOGLE_API_KEY")
        if google_key and GOOGLE_AVAILABLE:
            # Langchain wrapper for embeddings
            self.embedding_model = GoogleGenerativeAIEmbeddings(
                model="models/gemini-embedding-001",
                google_api_key=google_key
            )
            # Custom function wrapper for ChromaDB
            self.embedding_fn = self._google_embedding_fn
            
        # 2. OpenAI Embeddings (Fallback)
        elif os.getenv("OPENAI_API_KEY") and OPENAI_AVAILABLE:
            self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            self.embedding_fn = self._openai_embedding_fn
        
        # ChromaDB 초기화
        if CHROMADB_AVAILABLE:
            self.client = chromadb.PersistentClient(path=persist_dir)
            self.collection = self.client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"description": "BioLinker RFP Notice Embeddings"}
            )
    
    def _google_embedding_fn(self, input):
        """Wrapper for Google Embeddings for ChromaDB"""
        if isinstance(input, str):
            input = [input]
        return self.embedding_model.embed_documents(input)

    def _openai_embedding_fn(self, input):
        """Wrapper for OpenAI Embeddings"""
        if isinstance(input, str):
            input = [input]
        data = []
        for text in input:
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text[:8000]
            )
            data.append(response.data[0].embedding)
        return data

    
    def _get_embedding(self, text: str) -> list[float]:
        """단일 텍스트 임베딩 생성"""
        if self.embedding_fn:
            return self.embedding_fn([text])[0]
        
        # Mock embedding
        import hashlib
        hash_val = hashlib.md5(text.encode()).hexdigest()
        return [float(int(hash_val[i:i+2], 16)) / 255 for i in range(0, 32, 2)]
    
    def add_notice(self, rfp: RFPDocument) -> str:
        """공고 저장"""
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
        
        if CHROMADB_AVAILABLE and self.collection:
            # ChromaDB 저장
            self.collection.add(
                ids=[rfp.id],
                embeddings=[embedding],
                metadatas=[metadata],
                documents=[rfp.body_text[:5000]]
            )
        else:
            # Simple In-Memory JSON 저장
            self._save_to_json(rfp.id, embedding, metadata, rfp.body_text[:5000])
        
        return rfp.id
    
    def add_notices(self, rfps: list[RFPDocument]) -> list[str]:
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
        query_embedding = self._get_embedding(query)
        
        if CHROMADB_AVAILABLE and self.collection:
            # ChromaDB 검색
            where = {"source": source_filter} if source_filter else None
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where,
                include=["metadatas", "documents", "distances"]
            )
            notices = []
            for i, doc_id in enumerate(results['ids'][0]):
                notices.append({
                    'id': doc_id,
                    'metadata': results['metadatas'][0][i],
                    'document': results['documents'][0][i][:500],
                    'similarity': 1 - results['distances'][0][i]
                })
            return notices
        else:
            # Simple In-Memory 검색
            return self._search_in_memory(query_embedding, n_results, source_filter)
    
    def _save_to_json(self, doc_id, embedding, metadata, document):
        """In-Memory 저장 (JSON)"""
        import json
        import numpy as np
        
        db_path = os.path.join(self.persist_dir, "db.json")
        os.makedirs(self.persist_dir, exist_ok=True)
        
        data = {}
        if os.path.exists(db_path):
            with open(db_path, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                except:
                    pass
        
        data[doc_id] = {
            "embedding": embedding,
            "metadata": metadata,
            "document": document
        }
        
        with open(db_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)

    def _search_in_memory(self, query_embedding, n_results, source_filter):
        """In-Memory 코사인 유사도 검색"""
        import json
        import numpy as np
        
        db_path = os.path.join(self.persist_dir, "db.json")
        if not os.path.exists(db_path):
            return []
            
        with open(db_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        results = []
        q_vec = np.array(query_embedding)
        q_norm = np.linalg.norm(q_vec)
        
        for doc_id, item in data.items():
            if source_filter and item['metadata'].get('source') != source_filter:
                continue
                
            d_vec = np.array(item['embedding'])
            d_norm = np.linalg.norm(d_vec)
            
            if q_norm == 0 or d_norm == 0:
                sim = 0
            else:
                sim = np.dot(q_vec, d_vec) / (q_norm * d_norm)
                
            results.append({
                'id': doc_id,
                'metadata': item['metadata'],
                'document': item['document'],
                'similarity': float(sim)
            })
            
        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:n_results]

    def search_by_profile(
        self,
        tech_keywords: list[str],
        tech_description: str,
        n_results: int = 10
    ) -> list[dict]:
        query = f"기술 키워드: {', '.join(tech_keywords)}\n역량: {tech_description}"
        return self.search_similar(query, n_results)
    
    def get_notice(self, notice_id: str) -> Optional[dict]:
        """ID로 공고 조회"""
        if CHROMADB_AVAILABLE and self.collection:
            try:
                result = self.collection.get(ids=[notice_id], include=["metadatas", "documents"])
                if result['ids']:
                    return {
                        'id': notice_id,
                        'metadata': result['metadatas'][0],
                        'document': result['documents'][0]
                    }
            except:
                pass
        else:
            # Check JSON
            import json
            db_path = os.path.join(self.persist_dir, "db.json")
            if os.path.exists(db_path):
                with open(db_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if notice_id in data:
                        return {
                            'id': notice_id,
                            'metadata': data[notice_id]['metadata'],
                            'document': data[notice_id]['document']
                        }
        return None
    
    def delete_notice(self, notice_id: str):
        if CHROMADB_AVAILABLE and self.collection:
            self.collection.delete(ids=[notice_id])
        else:
            import json
            db_path = os.path.join(self.persist_dir, "db.json")
            if os.path.exists(db_path):
                with open(db_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if notice_id in data:
                    del data[notice_id]
                    with open(db_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False)

    def count(self) -> int:
        if CHROMADB_AVAILABLE and self.collection:
            return self.collection.count()
        else:
            import json
            db_path = os.path.join(self.persist_dir, "db.json")
            if os.path.exists(db_path):
                with open(db_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return len(data)
            return 0
    
    def list_all(self, limit: int = 100) -> list[dict]:
        if CHROMADB_AVAILABLE and self.collection:
            result = self.collection.get(limit=limit, include=["metadatas"])
            return [{'id': id_, 'metadata': meta} for id_, meta in zip(result['ids'], result['metadatas'])]
        else:
            import json
            db_path = os.path.join(self.persist_dir, "db.json")
            if os.path.exists(db_path):
                with open(db_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return [{'id': k, 'metadata': v['metadata']} for k, v in list(data.items())[:limit]]
            return []


# Singleton
_vector_store: Optional[VectorStore] = None

def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
