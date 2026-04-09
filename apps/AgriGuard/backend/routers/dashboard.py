from datetime import UTC, datetime

import models
import schemas
from dependencies import get_cache, get_db
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload


router = APIRouter()

# Fallback values used when the DB has no real data yet (demo mode)
DEMO_TOTAL_FARMS = 142
DEMO_SENSORS_PER_PRODUCT = 3
DEMO_ACTIVE_SENSORS = 450
DEMO_ACTIVE_CYCLES = 25
DEMO_COMPLETED_CYCLES = 102


def _get_latest_status_per_product(product: models.Product) -> str | None:
    if not product.tracking_history:
        return None
    return max(product.tracking_history, key=lambda event: event.timestamp).status


def _build_status_distribution(products: list[models.Product]) -> dict:
    distribution = {}
    for product in products:
        latest_status = _get_latest_status_per_product(product)
        if latest_status:
            distribution[latest_status] = distribution.get(latest_status, 0) + 1
    return distribution


def _build_origin_distribution(products: list[models.Product]) -> dict:
    distribution = {}
    for product in products:
        origin = product.origin or "Unknown"
        distribution[origin] = distribution.get(origin, 0) + 1
    return distribution


def _format_tracking_event_as_activity(event: models.TrackingEvent) -> dict:
    return {
        "timestamp": event.timestamp.isoformat() + "Z",
        "event": f"Product {event.product_id[:8]} status changed to {event.status} at {event.location}",
    }


@router.get("/")
def read_root():
    return {"message": "Welcome to AgriGuard API (DB Connected)", "status": "running"}


@router.get("/api/v1/dashboard/summary", response_model=schemas.DashboardResponse)
async def get_frontend_dashboard_summary(db: Session = Depends(get_db)):
    cache = get_cache()
    cached = await cache.get("agriguard:dashboard:frontend")
    if cached is not None:
        return cached

    farmer_count = db.query(models.User).filter(models.User.role == "Farmer").count()
    total_products = db.query(models.Product).count()
    harvested_products = (
        db.query(models.Product)
        .filter(models.Product.harvest_date != None)  # noqa: E711 - SQLAlchemy uses IS NOT NULL here
        .count()
    )
    active_cycles = total_products - harvested_products

    recent_events = (
        db.query(models.TrackingEvent)
        .order_by(models.TrackingEvent.timestamp.desc())
        .limit(5)
        .all()
    )
    recent_activity = [_format_tracking_event_as_activity(event) for event in recent_events]

    if not recent_activity:
        recent_activity = [
            {
                "timestamp": datetime.now(UTC).isoformat() + "Z",
                "event": "System initialized. Waiting for sensor data.",
            }
        ]

    has_real_data = total_products > 0
    result = {
        "status": "success",
        "data": {
            "total_farms": farmer_count if has_real_data else DEMO_TOTAL_FARMS,
            "active_sensors": total_products * DEMO_SENSORS_PER_PRODUCT if has_real_data else DEMO_ACTIVE_SENSORS,
            "critical_alerts": 0,
            "growth_cycles": {
                "active": active_cycles if has_real_data else DEMO_ACTIVE_CYCLES,
                "completed": harvested_products if has_real_data else DEMO_COMPLETED_CYCLES,
            },
            "recent_activity": recent_activity,
        },
    }
    await cache.set("agriguard:dashboard:frontend", result, ttl=30)
    return result


@router.get("/dashboard/summary")
async def get_supply_chain_summary(db: Session = Depends(get_db)):
    cache = get_cache()
    cached = await cache.get("agriguard:dashboard:supply_chain")
    if cached is not None:
        return cached

    products = (
        db.query(models.Product)
        .options(
            selectinload(models.Product.certificates),
            selectinload(models.Product.tracking_history),
        )
        .all()
    )

    certified_count = sum(1 for product in products if product.certificates)
    cold_chain_count = sum(1 for product in products if product.requires_cold_chain)
    total_tracking_events = sum(len(product.tracking_history) for product in products)

    result = {
        "total_products": len(products),
        "certified_products": certified_count,
        "cold_chain_products": cold_chain_count,
        "total_tracking_events": total_tracking_events,
        "status_distribution": _build_status_distribution(products),
        "origin_distribution": _build_origin_distribution(products),
    }
    await cache.set("agriguard:dashboard:supply_chain", result, ttl=30)
    return result
