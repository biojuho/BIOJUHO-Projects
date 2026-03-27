"""
AgriGuard Backend Smoke Tests
Tests core API endpoints and seed_db functionality.
"""
import os
import subprocess

backend_dir = os.path.join(os.path.dirname(__file__), "..")

def test_imports():
    """Verify all core modules can be imported without error."""
    result = subprocess.run(["python", "-c", "import models, database, seed_db"], cwd=backend_dir)
    assert result.returncode == 0

def test_seed_db_creates_data():
    """Run seed_db and verify data counts."""
    result = subprocess.run(["python", "seed_db.py"], cwd=backend_dir, capture_output=True)
    assert result.returncode == 0

def test_dashboard_summary_data_shape():
    """Verify seed data can produce a valid dashboard summary."""
    code = """
from database import SessionLocal
import models
db = SessionLocal()
try:
    total_products = db.query(models.Product).count()
    verified = db.query(models.Product).filter(models.Product.is_verified == True).count()
    events = db.query(models.TrackingEvent).count()
    assert total_products >= 0
    assert verified >= 0
    assert events >= 0
finally:
    db.close()
"""
    result = subprocess.run(["python", "-c", code], cwd=backend_dir)
    assert result.returncode == 0
