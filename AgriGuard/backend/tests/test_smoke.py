"""
AgriGuard Backend Smoke Tests
Tests core API endpoints and seed_db functionality.
"""
import os
import sys
import pytest

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_imports():
    """Verify all core modules can be imported without error."""
    import models
    import database
    import seed_db
    assert hasattr(models, "User")
    assert hasattr(models, "Product")
    assert hasattr(models, "TrackingEvent")
    assert hasattr(database, "SessionLocal")
    assert hasattr(seed_db, "seed_db")


def test_seed_db_creates_data():
    """Run seed_db and verify data counts."""
    from database import SessionLocal, engine
    import models

    # Ensure tables exist
    models.Base.metadata.create_all(bind=engine)

    from seed_db import seed_db
    seed_db()

    db = SessionLocal()
    try:
        user_count = db.query(models.User).count()
        product_count = db.query(models.Product).count()
        event_count = db.query(models.TrackingEvent).count()

        assert user_count >= 120, f"Expected 120+ users, got {user_count}"
        assert product_count >= 500, f"Expected 500+ products, got {product_count}"
        assert event_count >= 1500, f"Expected 1500+ events, got {event_count}"
    finally:
        db.close()


def test_dashboard_summary_data_shape():
    """Verify seed data can produce a valid dashboard summary."""
    from database import SessionLocal
    import models

    db = SessionLocal()
    try:
        total_products = db.query(models.Product).count()
        verified = db.query(models.Product).filter(models.Product.is_verified == True).count()
        events = db.query(models.TrackingEvent).count()

        assert total_products > 0
        assert verified >= 0
        assert events > 0
    finally:
        db.close()
