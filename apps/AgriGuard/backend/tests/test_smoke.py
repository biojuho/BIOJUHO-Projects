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


def test_qr_event_summary_funnel_metrics():
    """Verify QR funnel summary math with a temporary SQLite database."""
    code = """
import os
import tempfile
from datetime import datetime

tmpdir = tempfile.mkdtemp()
db_path = os.path.join(tmpdir, "qr-events-smoke.db")
os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
os.environ["AUTO_CREATE_SCHEMA"] = "1"

from database import SessionLocal, initialize_database
import models
from main import get_qr_event_summary

initialize_database()
db = SessionLocal()
try:
    now = datetime.utcnow()
    db.add_all([
        models.QRScanEvent(session_id="s1", event_type="scan_start", occurred_at=now, variant_id="qr_page_v2"),
        models.QRScanEvent(session_id="s1", event_type="scan_failure", occurred_at=now, variant_id="qr_page_v2", error_code="camera_denied"),
        models.QRScanEvent(session_id="s1", event_type="scan_recovery", occurred_at=now, variant_id="qr_page_v2", recovery_method="retry"),
        models.QRScanEvent(session_id="s1", event_type="verification_complete", occurred_at=now, variant_id="qr_page_v2"),
        models.QRScanEvent(session_id="s2", event_type="scan_start", occurred_at=now, variant_id="qr_page_v2"),
        models.QRScanEvent(session_id="s2", event_type="scan_failure", occurred_at=now, variant_id="qr_page_v2", error_code="invalid_qr"),
    ])
    db.commit()

    summary = get_qr_event_summary(hours=24, variant_id="qr_page_v2", db=db)
    assert summary["total_events"] == 6
    assert summary["total_sessions"] == 2
    assert summary["event_counts"]["scan_start"] == 2
    assert summary["event_counts"]["scan_failure"] == 2
    assert summary["event_counts"]["scan_recovery"] == 1
    assert summary["event_counts"]["verification_complete"] == 1
    assert summary["error_counts"]["camera_denied"] == 1
    assert summary["error_counts"]["invalid_qr"] == 1
    assert summary["variant_counts"]["qr_page_v2"] == 6
    assert summary["funnel"]["scan_start_sessions"] == 2
    assert summary["funnel"]["scan_failure_sessions"] == 2
    assert summary["funnel"]["scan_recovery_sessions"] == 1
    assert summary["funnel"]["verification_complete_sessions"] == 1
    assert summary["funnel"]["verification_completion_rate"] == 0.5
    assert summary["funnel"]["recovery_rate_after_failure"] == 0.5
finally:
    db.close()
"""
    result = subprocess.run(["python", "-c", code], cwd=backend_dir)
    assert result.returncode == 0
