"""Hashtag strategy router — Hashtag optimization endpoints.

Routes for generating optimized hashtag sets and analyzing performance.

Endpoints:
- GET  /api/hashtags/generate  Get optimized hashtag set
- GET  /api/hashtags/top       Top performing hashtags
- POST /api/hashtags/seed      Seed default hashtag pools
- GET  /api/hashtags/stats     Hashtag database statistics
"""

from __future__ import annotations

from dependencies import get_hashtag_db
from fastapi import APIRouter, Depends, Query
from services.hashtag_strategy import HashtagDB

router = APIRouter(prefix="/api/hashtags", tags=["hashtags"])


# ---- Route Handlers ----


@router.get("/generate")
async def generate_hashtag_set(
    niche: str = Query("tech"),
    count: int = Query(15, ge=5, le=30),
    hashtag_db: HashtagDB = Depends(get_hashtag_db),
):
    """Get an optimized hashtag set for a niche.

    Args:
        niche: Content niche/category
        count: Number of hashtags to generate (5-30)
        hashtag_db: Hashtag database dependency

    Returns:
        Optimized hashtag set with formatted string
    """
    tags = hashtag_db.get_optimized_set(niche=niche, count=count)
    return {
        "niche": niche,
        "count": len(tags),
        "hashtags": tags,
        "as_string": " ".join(tags),
    }


@router.get("/top")
async def top_hashtags(
    niche: str = Query("tech"),
    limit: int = Query(10),
    hashtag_db: HashtagDB = Depends(get_hashtag_db),
):
    """Get top-performing hashtags.

    Args:
        niche: Content niche/category
        limit: Maximum number of hashtags to return
        hashtag_db: Hashtag database dependency

    Returns:
        Top performing hashtags with performance metrics
    """
    return hashtag_db.get_top_performers(niche=niche, limit=limit)


@router.post("/seed")
async def seed_hashtags(hashtag_db: HashtagDB = Depends(get_hashtag_db)):
    """Seed default hashtag pools.

    Args:
        hashtag_db: Hashtag database dependency

    Returns:
        Number of hashtags seeded
    """
    count = hashtag_db.seed_defaults()
    return {"seeded": count}


@router.get("/stats")
async def hashtag_stats(hashtag_db: HashtagDB = Depends(get_hashtag_db)):
    """Hashtag database statistics.

    Args:
        hashtag_db: Hashtag database dependency

    Returns:
        Hashtag database statistics and metrics
    """
    return hashtag_db.get_stats()
