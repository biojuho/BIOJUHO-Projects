"""Posts router — Instagram post management endpoints.

Endpoints:
- POST /api/posts/generate  Generate content batch
- POST /api/posts/enqueue   Manually enqueue a post
- GET  /api/posts/queue     View post queue
- POST /api/posts/publish   Trigger next publish
- GET  /api/posts/published View recently published posts
"""

from __future__ import annotations

from datetime import datetime

from dependencies import get_database, get_scheduler
from fastapi import APIRouter, Depends, Query
from models import InstagramPost, PostType
from pydantic import BaseModel
from services.database import Database
from services.scheduler import PostScheduler

router = APIRouter(prefix="/api/posts", tags=["posts"])


# ---- Pydantic Models ----


class GenerateRequest(BaseModel):
    topics: list[str] = []


class EnqueueRequest(BaseModel):
    caption: str
    hashtags: str = ""
    image_url: str | None = None
    video_url: str | None = None
    carousel_urls: list[str] = []
    post_type: str = "IMAGE"
    scheduled_at: str | None = None  # ISO format


# ---- Route Handlers ----


@router.post("/generate")
async def generate_content(
    req: GenerateRequest,
    scheduler: PostScheduler = Depends(get_scheduler),
    db: Database = Depends(get_database),
):
    """Generate daily content batch."""
    count = await scheduler.generate_daily_content(topics=req.topics if req.topics else None)
    return {"generated": count, "queue": len(db.get_queued_posts())}


@router.post("/enqueue")
async def enqueue_post(
    req: EnqueueRequest,
    db: Database = Depends(get_database),
):
    """Manually enqueue a post."""
    post = InstagramPost(
        caption=req.caption,
        hashtags=req.hashtags,
        image_url=req.image_url,
        video_url=req.video_url,
        carousel_urls=req.carousel_urls,
        post_type=PostType(req.post_type),
        scheduled_at=datetime.fromisoformat(req.scheduled_at) if req.scheduled_at else None,
    )
    post_id = db.enqueue_post(post)
    return {"post_id": post_id, "status": "queued"}


@router.get("/queue")
async def get_queue(db: Database = Depends(get_database)):
    """View current post queue."""
    posts = db.get_queued_posts()
    return {
        "count": len(posts),
        "posts": [
            {
                "id": p.id,
                "caption_preview": p.caption[:100],
                "post_type": p.post_type.value,
                "scheduled_at": p.scheduled_at.isoformat() if p.scheduled_at else None,
                "has_image": bool(p.image_url),
                "has_video": bool(p.video_url),
            }
            for p in posts
        ],
    }


@router.post("/publish")
async def trigger_publish(scheduler: PostScheduler = Depends(get_scheduler)):
    """Manually trigger publishing the next queued post."""
    success = await scheduler.publish_next()
    return {"published": success}


@router.get("/published")
async def get_published(
    limit: int = Query(20, ge=1, le=100),
    db: Database = Depends(get_database),
):
    """View recently published posts."""
    posts = db.get_published_posts(limit=limit)
    return {
        "count": len(posts),
        "posts": [
            {
                "id": p.id,
                "media_id": p.media_id,
                "caption_preview": p.caption[:100],
                "post_type": p.post_type.value,
                "published_at": p.published_at.isoformat() if p.published_at else None,
            }
            for p in posts
        ],
    }
