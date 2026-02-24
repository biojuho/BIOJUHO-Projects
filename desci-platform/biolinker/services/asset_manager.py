
import os
import shutil
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import UploadFile

from .pdf_parser import get_pdf_parser
from .vector_store import get_vector_store

class AssetManager:
    """회사 자산(IR, 논문, 특허 등) 관리 및 인덱싱 서비스"""
    
    def __init__(self, asset_dir: str = "data/assets"):
        self.asset_dir = asset_dir
        os.makedirs(self.asset_dir, exist_ok=True)
        self.vector_store = get_vector_store()
        self.pdf_parser = get_pdf_parser()

    async def upload_asset(self, file: UploadFile, asset_type: str = "general") -> Dict[str, Any]:
        """
        파일 업로드 및 벡터 DB 인덱싱
        
        Args:
            file: 업로드된 파일 객체
            asset_type: 자산 유형 (ir, paper, patent, etc.)
            
        Returns:
            Dict: 업로드 결과 (id, filename, status)
        """
        # 1. Generate ID & Path
        asset_id = str(uuid.uuid4())
        file_ext = os.path.splitext(file.filename)[1]
        saved_filename = f"{asset_id}{file_ext}"
        file_path = os.path.join(self.asset_dir, saved_filename)
        
        # 2. Save File Locally
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
            
        # 3. Parse Text (if PDF)
        text_content = ""
        if file_ext.lower() == ".pdf":
            text_content = self.pdf_parser.parse(content)
        else:
            # Fallback for text files
            try:
                text_content = content.decode("utf-8")
            except (UnicodeDecodeError, AttributeError):
                text_content = ""
                
        if not text_content:
            text_content = "No text content extracted."

        # 4. Index to Vector Store
        # We misuse 'add_paper' or create a new method 'add_asset' in VectorStore?
        # For now, let's use a custom add logic here or adapt VectorStore to be generic.
        # Since VectorStore is focused on RFPs/Papers, let's add a generic 'add_document' method to VectorStore later.
        # For now, we will simulate it by adding it as a 'paper' with type metadata.
        
        # Construct Metadata
        metadata = {
            "type": "company_asset",
            "asset_type": asset_type,   # ir, patent, paper
            "original_filename": file.filename,
            "uploaded_at": datetime.now().isoformat(),
            "source": "UserUpload"
        }
        
        # Use existing add_paper but with custom metadata? 
        # VectorStore.add_paper takes specific args.
        # Let's add a generic indexing method to VectorStore to support this cleanly.
        # For now, I will use `add_paper` as a workaround but it's not ideal.
        # BETTER: I will add `add_company_asset` to VectorStore in the next step.
        
        self.vector_store.add_company_asset(
            asset_id=asset_id,
            title=file.filename,
            content=text_content,
            metadata=metadata
        )
        
        return {
            "id": asset_id,
            "filename": file.filename,
            "type": asset_type,
            "size": len(content),
            "indexed": bool(text_content)
        }

    def list_assets(self) -> List[Dict[str, Any]]:
        """저장된 자산 목록 조회 (VectorDB 메타데이터 기반)"""
        # This requires VectorStore to support querying by type.
        # For MVP, we can list files in the directory or query ChromaDB.
        # Let's list files for now as a simple source of truth.
        assets = []
        if os.path.exists(self.asset_dir):
            for f in os.listdir(self.asset_dir):
                if f.endswith(".pdf") or f.endswith(".txt"):
                    assets.append({"filename": f, "path": os.path.join(self.asset_dir, f)})
        return assets

    def delete_asset(self, asset_id: str):
        """자산 삭제"""
        # 1. Delete from VectorDB
        self.vector_store.delete_notice(asset_id) # delete_notice is generic ID delete
        
        # 2. Delete local file
        # Iterate to find the file with this ID prefix
        for f in os.listdir(self.asset_dir):
            if f.startswith(asset_id):
                os.remove(os.path.join(self.asset_dir, f))
                break

# Singleton
_asset_manager = None

def get_asset_manager():
    global _asset_manager
    if _asset_manager is None:
        _asset_manager = AssetManager()
    return _asset_manager
