"""
BioLinker - RFP Crawler Service
정부 과제 공고 수집 및 파싱
"""
import os
import re
import uuid
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import RFPDocument

# Optional imports for web crawling
try:
    import aiohttp
    from bs4 import BeautifulSoup
    CRAWLING_AVAILABLE = True
except ImportError:
    CRAWLING_AVAILABLE = False


class RFPCrawler:
    """정부 과제 공고 크롤러"""
    
    # 알려진 공고 출처 매핑
    SOURCE_PATTERNS = {
        "kddf": "KDDF",
        "ntis": "NTIS",
        "tips": "TIPS",
        "keit": "KEIT",
        "nrf": "NRF",
        "nipa": "NIPA",
        "k-bds": "K-BDS",
    }
    
    def __init__(self):
        self.session = None
    
    async def _get_session(self):
        if self.session is None and CRAWLING_AVAILABLE:
            self.session = aiohttp.ClientSession()
        return self.session
    
    def _detect_source(self, text: str, url: Optional[str] = None) -> str:
        """공고 출처 자동 감지"""
        if url:
            domain = urlparse(url).netloc.lower()
            for pattern, source in self.SOURCE_PATTERNS.items():
                if pattern in domain:
                    return source
        
        # 텍스트에서 출처 추출
        for pattern, source in self.SOURCE_PATTERNS.items():
            if pattern.upper() in text.upper():
                return source
        
        return "기타"
    
    def _extract_keywords(self, text: str) -> list[str]:
        """본문에서 핵심 키워드 추출"""
        # 바이오 관련 키워드 패턴
        bio_keywords = [
            "신약", "바이오", "의약품", "임상", "전임상", "치료제",
            "항체", "단백질", "유전자", "세포", "줄기세포", "CAR-T",
            "mRNA", "펩타이드", "플랫폼", "진단", "AI", "디지털",
            "TRL", "GMP", "FDA", "MFDS", "IND", "NDA", "CMC"
        ]
        
        found = []
        text_upper = text.upper()
        for kw in bio_keywords:
            if kw.upper() in text_upper:
                found.append(kw)
        
        return found[:10]  # 최대 10개
    
    def _extract_deadline(self, text: str) -> Optional[datetime]:
        """마감일 추출"""
        # 날짜 패턴 (YYYY.MM.DD, YYYY-MM-DD, YYYY년 MM월 DD일)
        patterns = [
            r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})',
            r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                try:
                    year, month, day = map(int, matches[-1])  # 마지막 날짜가 마감일일 가능성 높음
                    return datetime(year, month, day)
                except:
                    pass
        
        return None
    
    def _extract_eligibility(self, text: str) -> list[str]:
        """지원 자격 조건 추출"""
        eligibility = []
        
        # 자격 관련 키워드 패턴
        patterns = [
            r'지원\s*자격[:\s]*(.*?)(?:\n|$)',
            r'참여\s*자격[:\s]*(.*?)(?:\n|$)',
            r'신청\s*자격[:\s]*(.*?)(?:\n|$)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            eligibility.extend(matches)
        
        # 일반적인 자격 조건 추출
        if "중소기업" in text:
            eligibility.append("중소기업")
        if "벤처기업" in text:
            eligibility.append("벤처기업")
        if "컨소시엄" in text:
            eligibility.append("컨소시엄 구성 필요")
        
        return list(set(eligibility))[:5]
    
    def _extract_required_docs(self, text: str) -> list[str]:
        """필수 제출 서류 추출"""
        docs = []
        
        doc_keywords = [
            "사업계획서", "기술성 평가서", "재무제표", "법인등기부등본",
            "연구개발계획서", "사업자등록증", "특허 증빙", "기업 소개서"
        ]
        
        for doc in doc_keywords:
            if doc in text:
                docs.append(doc)
        
        return docs if docs else ["사업계획서", "기업 소개서"]
    
    async def parse_text(self, text: str, url: Optional[str] = None) -> RFPDocument:
        """
        텍스트에서 RFP 문서 파싱
        
        Args:
            text: 공고문 텍스트
            url: 공고 URL (선택)
            
        Returns:
            RFPDocument: 정규화된 공고 데이터
        """
        # 제목 추출 (첫 줄 또는 [공고] 패턴)
        lines = text.strip().split('\n')
        title = lines[0].strip() if lines else "제목 없음"
        
        # [공고] 패턴 찾기
        title_match = re.search(r'\[공고\]\s*(.+)', text)
        if title_match:
            title = title_match.group(1).strip()
        
        return RFPDocument(
            id=str(uuid.uuid4()),
            title=title[:200],
            source=self._detect_source(text, url),
            deadline=self._extract_deadline(text),
            budget_range=self._extract_budget(text),
            body_text=text,
            keywords=self._extract_keywords(text),
            eligibility=self._extract_eligibility(text),
            required_docs=self._extract_required_docs(text),
            url=url
        )
    
    def _extract_budget(self, text: str) -> Optional[str]:
        """지원 규모 추출"""
        patterns = [
            r'(\d+[,\d]*)\s*억\s*원',
            r'(\d+[,\d]*)\s*만\s*원',
            r'총\s*사업비[:\s]*(\d+[,\d]*)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        
        return None
    
    async def fetch_url(self, url: str) -> RFPDocument:
        """
        URL에서 공고문 크롤링
        
        Args:
            url: 공고 URL
            
        Returns:
            RFPDocument: 파싱된 공고 데이터
        """
        if not CRAWLING_AVAILABLE:
            raise RuntimeError("aiohttp와 beautifulsoup4가 필요합니다")
        
        session = await self._get_session()
        async with session.get(url) as response:
            html = await response.text()
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # 텍스트 추출 (스크립트, 스타일 제거)
        for tag in soup(['script', 'style', 'nav', 'header', 'footer']):
            tag.decompose()
        
        text = soup.get_text(separator='\n', strip=True)
        
        return await self.parse_text(text, url)
    
    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None


# Singleton instance
_crawler: Optional[RFPCrawler] = None

def get_crawler() -> RFPCrawler:
    global _crawler
    if _crawler is None:
        _crawler = RFPCrawler()
    return _crawler
