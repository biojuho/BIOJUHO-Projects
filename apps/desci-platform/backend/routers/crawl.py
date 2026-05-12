"""
BioLinker - Crawl Router.

Service imports stay inside endpoint handlers so the app can boot in lean
smoke environments that do not install every crawler dependency.
"""

from fastapi import APIRouter, Request

from limiter import limiter

router = APIRouter()


def get_scheduler():
    from services.scheduler import get_scheduler as _get_scheduler

    return _get_scheduler()


def get_kddf_crawler():
    from services.kddf_crawler import get_kddf_crawler as _get_kddf_crawler

    return _get_kddf_crawler()


def get_ntis_crawler():
    from services.ntis_crawler import get_ntis_crawler as _get_ntis_crawler

    return _get_ntis_crawler()


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
    source: str | None = None,
    limit: int = 30,
):
    """Return previously collected government RFP notices."""

    scheduler = get_scheduler()
    return scheduler.get_notices(source=source, limit=limit)


@router.post("/notices/collect", tags=["Crawling"])
async def collect_notices():
    """Collect KDDF/NTIS notices on demand."""

    scheduler = get_scheduler()
    notices = await scheduler.collect_all_notices()
    return {"collected": len(notices), "notices": notices[:10]}


@router.get("/notices/kddf", tags=["Crawling"])
async def get_kddf_notices(page: int = 1):
    """Return raw KDDF notices."""

    crawler = get_kddf_crawler()
    return await crawler.fetch_notice_list(page)


@router.get("/notices/ntis", tags=["Crawling"])
async def get_ntis_notices(keyword: str = "bio", page: int = 1):
    """Return raw NTIS notices."""

    crawler = get_ntis_crawler()
    return await crawler.fetch_notice_list(keyword, page)
