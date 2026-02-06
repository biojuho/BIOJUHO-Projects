"""
BioLinker - NTIS Crawler
국가과학기술정보서비스 공고 크롤러
"""
import os
import re
import uuid
import asyncio
from datetime import datetime
from typing import Optional

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import RFPDocument

try:
    import aiohttp
    from bs4 import BeautifulSoup
    CRAWLING_AVAILABLE = True
except ImportError:
    CRAWLING_AVAILABLE = False


class NTISCrawler:
    """NTIS 공고 크롤러"""
    
    # NTIS 바이오 분야 공고 검색
    BASE_URL = "https://www.ntis.go.kr"
    SEARCH_URL = "https://www.ntis.go.kr/rndgate/eg/un/ra/mng/selectRndAnnoList.do"
    
    def __init__(self):
        self.session = None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/x-www-form-urlencoded"
        }
    
    async def _get_session(self):
        if self.session is None and CRAWLING_AVAILABLE:
            self.session = aiohttp.ClientSession(headers=self.headers)
        return self.session
    
    async def fetch_notice_list(self, keyword: str = "바이오", page: int = 1) -> list[dict]:
        """공고 목록 검색"""
        if not CRAWLING_AVAILABLE:
            return self._get_mock_notices()
        
        try:
            session = await self._get_session()
            
            # NTIS 검색 파라미터
            data = {
                'searchKeyword': keyword,
                'pageIndex': page,
                'pageUnit': 10,
                'annoStatus': '접수중'  # 접수중인 공고만
            }
            
            async with session.post(self.SEARCH_URL, data=data) as response:
                html = await response.text()
            
            soup = BeautifulSoup(html, 'html.parser')
            notices = []
            
            # 공고 목록 파싱
            items = soup.select('.list_wrap li, table.board tbody tr')
            for item in items:
                try:
                    title_elem = item.select_one('a.title, td.title a')
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    link = title_elem.get('href', '')
                    
                    # 마감일 추출
                    deadline_elem = item.select_one('.deadline, td.date')
                    deadline = deadline_elem.get_text(strip=True) if deadline_elem else None
                    
                    # 지원 기관
                    agency_elem = item.select_one('.agency, td.agency')
                    agency = agency_elem.get_text(strip=True) if agency_elem else "NTIS"
                    
                    notices.append({
                        'title': title,
                        'url': link if link.startswith('http') else f"{self.BASE_URL}{link}",
                        'deadline': deadline,
                        'agency': agency,
                        'source': 'NTIS'
                    })
                except Exception:
                    continue
            
            return notices if notices else self._get_mock_notices()
            
        except Exception as e:
            print(f"[NTIS] Crawling error: {e}")
            return self._get_mock_notices()
    
    async def fetch_notice_detail(self, url: str) -> Optional[RFPDocument]:
        """공고 상세 내용"""
        if not CRAWLING_AVAILABLE:
            return None
        
        try:
            session = await self._get_session()
            async with session.get(url) as response:
                html = await response.text()
            
            soup = BeautifulSoup(html, 'html.parser')
            
            title_elem = soup.select_one('.view_title, h2.title, .subject')
            title = title_elem.get_text(strip=True) if title_elem else "제목 없음"
            
            content_elem = soup.select_one('.view_content, .content, .board_view')
            body = content_elem.get_text(separator='\n', strip=True) if content_elem else ""
            
            return RFPDocument(
                id=str(uuid.uuid4()),
                title=title,
                source="NTIS",
                body_text=body,
                url=url,
                keywords=self._extract_keywords(body),
                deadline=self._extract_deadline(body),
                budget_range=self._extract_budget(body)
            )
            
        except Exception as e:
            print(f"[NTIS] Detail fetch error: {e}")
            return None
    
    def _extract_keywords(self, text: str) -> list[str]:
        keywords = [
            "신약", "바이오", "의약품", "임상", "전임상", "치료제",
            "항체", "단백질", "유전자", "AI", "디지털헬스", "의료기기"
        ]
        return [kw for kw in keywords if kw in text][:8]
    
    def _extract_deadline(self, text: str) -> Optional[datetime]:
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
    
    def _extract_budget(self, text: str) -> Optional[str]:
        patterns = [
            r'(\d+[,\d]*)\s*억\s*원',
            r'총\s*사업비[:\s]*(\d+[,\d]*)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        return None
    
    def _get_mock_notices(self) -> list[dict]:
        """개발용 Mock 데이터"""
        return [
            {
                'title': '[NTIS] 범부처 신약개발사업 2024 공고',
                'url': 'https://www.ntis.go.kr/mock/1',
                'deadline': '2024-04-30',
                'agency': '범부처신약개발사업단',
                'source': 'NTIS'
            },
            {
                'title': '[NTIS] 바이오헬스 기술개발 지원사업',
                'url': 'https://www.ntis.go.kr/mock/2',
                'deadline': '2024-04-15',
                'agency': 'KEIT',
                'source': 'NTIS'
            },
            {
                'title': '[NTIS] AI 기반 신약 스크리닝 R&D',
                'url': 'https://www.ntis.go.kr/mock/3',
                'deadline': '2024-05-10',
                'agency': 'NRF',
                'source': 'NTIS'
            }
        ]
    
    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None


# Singleton
_ntis_crawler: Optional[NTISCrawler] = None

def get_ntis_crawler() -> NTISCrawler:
    global _ntis_crawler
    if _ntis_crawler is None:
        _ntis_crawler = NTISCrawler()
    return _ntis_crawler
