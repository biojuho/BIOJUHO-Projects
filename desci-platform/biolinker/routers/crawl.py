"""
BioLinker - Crawl Router
KDDF/NTIS 공고 크롤링 엔드포인트
"""
from typing import Optional
from fastapi import APIRouter, Request

from services.scheduler import get_scheduler
from services.kddf_crawler import get_kddf_crawler
from services.ntis_crawler import get_ntis_crawler
from limiter import limiter

router = APIRouter()


@router.get(
    "/notices",
    summary="List collected RFP notices",
    response_description="Array of RFP notice objects",
    tags=["Crawling"],
    responses={
        200: {
            "description": "Notices returned successfully",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": "kddf-001",
                            "title": "2024 Drug Development Support Program",
                            "source": "KDDF",
                            "deadline": "2024-12-31T23:59:59",
                            "keywords": ["drug", "clinical trial"],
                        }
                    ]
                }
            },
        }
    },
)
@limiter.limit("30/minute")
async def get_notices(
    request: Request,
    source: Optional[str] = None,
    limit: int = 30,
):
    """Return previously collected government RFP notices.

    Optionally filter by ``source`` (e.g. KDDF, NTIS) and cap the
    result count with ``limit``.
    """
    scheduler = get_scheduler()
    return scheduler.get_notices(source=source, limit=limit)


@router.post("/notices/collect", tags=["Crawling"])
async def collect_notices():
    """KDDF/NTIS 공고 수집 실행"""
    scheduler = get_scheduler()
    notices = await scheduler.collect_all_notices()
    return {"collected": len(notices), "notices": notices[:10]}


@router.get("/notices/kddf", tags=["Crawling"])
async def get_kddf_notices(page: int = 1):
    """KDDF 공고 크롤링"""
    crawler = get_kddf_crawler()
    return await crawler.fetch_notice_list(page)


@router.get("/notices/ntis", tags=["Crawling"])
async def get_ntis_notices(keyword: str = "바이오", page: int = 1):
    """NTIS 공고 크롤링"""
    crawler = get_ntis_crawler()
    return await crawler.fetch_notice_list(keyword, page)
