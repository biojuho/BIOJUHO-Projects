"""
BioLinker - KDDF Crawler
한국신약개발연구조합 공고 크롤러
"""
import os
import re
import uuid
import asyncio
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import RFPDocument

try:
    import aiohttp
    from bs4 import BeautifulSoup
    CRAWLING_AVAILABLE = True
except ImportError:
    CRAWLING_AVAILABLE = False


class KDDFCrawler:
    """KDDF 공고 크롤러"""
    
    BASE_URL = "https://www.kddf.org"
    NOTICE_URL = "https://www.kddf.org/kor/sub06/sub06_01.php"
    
    def __init__(self):
        self.session = None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    
    async def _get_session(self):
        if self.session is None and CRAWLING_AVAILABLE:
            self.session = aiohttp.ClientSession(headers=self.headers)
        return self.session
    
    async def fetch_notice_list(self, page: int = 1) -> list[dict]:
        """공고 목록 가져오기"""
        if not CRAWLING_AVAILABLE:
            return self._get_mock_notices()
        
        try:
            session = await self._get_session()
            url = f"{self.NOTICE_URL}?page={page}"
            
            async with session.get(url) as response:
                html = await response.text()
            
            soup = BeautifulSoup(html, 'html.parser')
            notices = []
            
            # 공고 테이블에서 항목 추출
            rows = soup.select('table.board_list tbody tr')
            for row in rows:
                try:
                    title_elem = row.select_one('td.title a')
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    link = title_elem.get('href', '')
                    
                    # 날짜 추출
                    date_elem = row.select_one('td.date')
                    date_str = date_elem.get_text(strip=True) if date_elem else None
                    
                    notices.append({
                        'title': title,
                        'url': urljoin(self.BASE_URL, link),
                        'date': date_str,
                        'source': 'KDDF'
                    })
                except Exception:
                    continue
            
            return notices if notices else self._get_mock_notices()
            
        except Exception as e:
            print(f"[KDDF] Crawling error: {e}")
            return self._get_mock_notices()
    
    async def fetch_notice_detail(self, url: str) -> Optional[RFPDocument]:
        """공고 상세 내용 가져오기"""
        if not CRAWLING_AVAILABLE:
            return None
        
        try:
            session = await self._get_session()
            async with session.get(url) as response:
                html = await response.text()
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # 제목 추출
            title_elem = soup.select_one('.view_title, .board_view h3, h2.title')
            title = title_elem.get_text(strip=True) if title_elem else "제목 없음"
            
            # 본문 추출
            content_elem = soup.select_one('.view_content, .board_view_content, .content')
            body = content_elem.get_text(separator='\n', strip=True) if content_elem else ""
            
            return RFPDocument(
                id=str(uuid.uuid4()),
                title=title,
                source="KDDF",
                body_text=body,
                url=url,
                keywords=self._extract_keywords(body),
                deadline=self._extract_deadline(body)
            )
            
        except Exception as e:
            print(f"[KDDF] Detail fetch error: {e}")
            return None
    
    def _extract_keywords(self, text: str) -> list[str]:
        """바이오 키워드 추출"""
        keywords = [
            "신약", "바이오", "임상", "전임상", "치료제", "항체",
            "mRNA", "AI", "디지털", "의료기기", "진단", "펩타이드"
        ]
        return [kw for kw in keywords if kw in text][:8]
    
    def _extract_deadline(self, text: str) -> Optional[datetime]:
        """마감일 추출"""
        patterns = [
            r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})',
            r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                try:
                    year, month, day = map(int, matches[-1])
                    return datetime(year, month, day)
                except:
                    pass
        return None
    
    def _get_mock_notices(self) -> list[dict]:
        """개발용 Mock 데이터"""
        return [
            {
                'title': '[KDDF] 2024년 바이오헬스 혁신기술 개발사업 공고',
                'url': 'https://www.kddf.org/mock/1',
                'date': '2024-03-15',
                'source': 'KDDF'
            },
            {
                'title': '[KDDF] 신약개발 지원사업 참여기업 모집',
                'url': 'https://www.kddf.org/mock/2',
                'date': '2024-03-10',
                'source': 'KDDF'
            },
            {
                'title': '[KDDF] 바이오 벤처 R&D 촉진 프로그램',
                'url': 'https://www.kddf.org/mock/3',
                'date': '2024-03-05',
                'source': 'KDDF'
            }
        ]
    
    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None


# Singleton
_kddf_crawler: Optional[KDDFCrawler] = None

def get_kddf_crawler() -> KDDFCrawler:
    global _kddf_crawler
    if _kddf_crawler is None:
        _kddf_crawler = KDDFCrawler()
    return _kddf_crawler
