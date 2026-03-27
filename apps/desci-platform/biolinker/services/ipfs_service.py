"""
BioLinker - IPFS Service
IPFS 탈중앙화 저장 서비스 (Pinata 연동)
"""
import os
import json
import hashlib
from datetime import datetime
from typing import Optional, BinaryIO
from dotenv import load_dotenv

load_dotenv()

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False


class IPFSService:
    """IPFS 파일 저장 서비스 (Pinata)"""
    
    PINATA_API_URL = "https://api.pinata.cloud"
    PINATA_GATEWAY = "https://gateway.pinata.cloud/ipfs"
    
    def __init__(self):
        self.api_key = os.getenv("PINATA_API_KEY")
        self.api_secret = os.getenv("PINATA_API_SECRET")
        self.jwt = os.getenv("PINATA_JWT")
        self.session = None
    
    @property
    def is_configured(self) -> bool:
        """Pinata 설정 여부"""
        return bool(self.jwt or (self.api_key and self.api_secret))
    
    async def _get_session(self):
        if self.session is None and AIOHTTP_AVAILABLE:
            headers = {}
            if self.jwt:
                headers["Authorization"] = f"Bearer {self.jwt}"
            else:
                headers["pinata_api_key"] = self.api_key
                headers["pinata_secret_api_key"] = self.api_secret
            self.session = aiohttp.ClientSession(headers=headers)
        return self.session
    
    async def upload_file(
        self, 
        file_path: str, 
        metadata: Optional[dict] = None
    ) -> dict:
        """
        파일을 IPFS에 업로드
        
        Args:
            file_path: 업로드할 파일 경로
            metadata: 추가 메타데이터
            
        Returns:
            {'cid': 'Qm...', 'url': 'https://...', 'size': 12345}
        """
        if not self.is_configured:
            return self._mock_upload(file_path, metadata)
        
        if not AIOHTTP_AVAILABLE:
            raise RuntimeError("aiohttp가 필요합니다")
        
        session = await self._get_session()
        
        # 파일 읽기
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        filename = os.path.basename(file_path)
        
        # Pinata 옵션
        pinata_options = {
            "cidVersion": 1
        }
        
        pinata_metadata = {
            "name": filename,
            "keyvalues": metadata or {}
        }
        
        # FormData 생성
        form = aiohttp.FormData()
        form.add_field('file', file_content, filename=filename)
        form.add_field('pinataOptions', json.dumps(pinata_options))
        form.add_field('pinataMetadata', json.dumps(pinata_metadata))
        
        # 업로드
        async with session.post(
            f"{self.PINATA_API_URL}/pinning/pinFileToIPFS",
            data=form
        ) as response:
            if response.status == 200:
                result = await response.json()
                cid = result['IpfsHash']
                return {
                    'cid': cid,
                    'url': f"{self.PINATA_GATEWAY}/{cid}",
                    'size': result.get('PinSize', len(file_content)),
                    'timestamp': result.get('Timestamp', datetime.now().isoformat())
                }
            else:
                error = await response.text()
                raise RuntimeError(f"IPFS upload failed: {error}")
    
    async def upload_json(
        self, 
        data: dict, 
        name: str = "metadata.json"
    ) -> dict:
        """
        JSON 데이터를 IPFS에 업로드
        
        Args:
            data: 업로드할 JSON 데이터
            name: 파일명
            
        Returns:
            {'cid': 'Qm...', 'url': 'https://...'}
        """
        if not self.is_configured:
            return self._mock_json_upload(data, name)
        
        session = await self._get_session()
        
        payload = {
            "pinataContent": data,
            "pinataMetadata": {"name": name}
        }
        
        async with session.post(
            f"{self.PINATA_API_URL}/pinning/pinJSONToIPFS",
            json=payload
        ) as response:
            if response.status == 200:
                result = await response.json()
                cid = result['IpfsHash']
                return {
                    'cid': cid,
                    'url': f"{self.PINATA_GATEWAY}/{cid}"
                }
            else:
                error = await response.text()
                raise RuntimeError(f"IPFS JSON upload failed: {error}")
    
    async def get_file(self, cid: str) -> bytes:
        """IPFS에서 파일 다운로드"""
        if not AIOHTTP_AVAILABLE:
            raise RuntimeError("aiohttp가 필요합니다")
        
        session = await self._get_session()
        
        async with session.get(f"{self.PINATA_GATEWAY}/{cid}") as response:
            if response.status == 200:
                return await response.read()
            else:
                raise RuntimeError(f"Failed to fetch CID: {cid}")
    
    async def unpin(self, cid: str) -> bool:
        """IPFS에서 파일 삭제 (unpin)"""
        if not self.is_configured:
            return True
        
        session = await self._get_session()
        
        async with session.delete(
            f"{self.PINATA_API_URL}/pinning/unpin/{cid}"
        ) as response:
            return response.status == 200
    
    async def list_pins(self, limit: int = 10) -> list[dict]:
        """고정된 파일 목록"""
        if not self.is_configured:
            return []
        
        session = await self._get_session()
        
        async with session.get(
            f"{self.PINATA_API_URL}/data/pinList",
            params={"pageLimit": limit, "status": "pinned"}
        ) as response:
            if response.status == 200:
                result = await response.json()
                return result.get('rows', [])
            return []
    
    def _mock_upload(self, file_path: str, metadata: Optional[dict]) -> dict:
        """개발용 Mock 업로드"""
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        
        # 파일 해시로 가상 CID 생성
        with open(file_path, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()[:32]
        
        mock_cid = f"Qm{file_hash}"
        
        return {
            'cid': mock_cid,
            'url': f"https://ipfs.io/ipfs/{mock_cid}",
            'size': file_size,
            'timestamp': datetime.now().isoformat(),
            '_mock': True,
            '_note': 'Pinata API 키를 설정하면 실제 IPFS에 업로드됩니다'
        }
    
    def _mock_json_upload(self, data: dict, name: str) -> dict:
        """개발용 Mock JSON 업로드"""
        data_str = json.dumps(data, sort_keys=True)
        data_hash = hashlib.sha256(data_str.encode()).hexdigest()[:32]
        mock_cid = f"Qm{data_hash}"
        
        return {
            'cid': mock_cid,
            'url': f"https://ipfs.io/ipfs/{mock_cid}",
            '_mock': True
        }
    
    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None


# 논문 메타데이터 스키마
class PaperMetadata:
    """연구 논문 메타데이터"""
    
    def __init__(
        self,
        title: str,
        authors: list[str],
        abstract: str,
        keywords: list[str],
        doi: Optional[str] = None,
        published_date: Optional[str] = None
    ):
        self.title = title
        self.authors = authors
        self.abstract = abstract
        self.keywords = keywords
        self.doi = doi
        self.published_date = published_date
    
    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "keywords": self.keywords,
            "doi": self.doi,
            "published_date": self.published_date,
            "uploaded_at": datetime.now().isoformat(),
            "schema_version": "1.0"
        }


# Singleton
_ipfs_service: Optional[IPFSService] = None

def get_ipfs_service() -> IPFSService:
    global _ipfs_service
    if _ipfs_service is None:
        _ipfs_service = IPFSService()
    return _ipfs_service
