import json
import sqlite3
from pathlib import Path

import pytest
from antigravity_mcp.state.checkpoint import CheckpointStore
from antigravity_mcp.state.db_client import CheckpointDBClient

# Mock settings for SQLite fallback
class MockSettings:
    supabase_database_url = ""
    pipeline_state_db = Path(":memory:")

@pytest.fixture
def mock_db_client(monkeypatch):
    monkeypatch.setattr("antigravity_mcp.state.db_client.get_settings", lambda: MockSettings())
    client = CheckpointDBClient()
    yield client
    client.close()

@pytest.fixture
def checkpoint_store(mock_db_client, monkeypatch):
    store = CheckpointStore()
    store.db = mock_db_client
    yield store
    store.close()

def test_checkpoint_save_and_load_sqlite(checkpoint_store):
    """Test saving and loading a checkpoint using the SQLite fallback."""
    job_id = "test_job_1"
    
    # 1. Save checkpoint
    payload = {"all_results": {"Tech": {"post": "test_post"}}}
    checkpoint_store.save_checkpoint(job_id, "test_pipeline", "step_1", payload)
    
    # 2. Load checkpoint
    step, loaded_payload = checkpoint_store.load_checkpoint(job_id)
    
    assert step == "step_1"
    assert loaded_payload["all_results"]["Tech"]["post"] == "test_post"

def test_checkpoint_update_sqlite(checkpoint_store):
    """Test updating an existing checkpoint."""
    job_id = "test_job_2"
    
    checkpoint_store.save_checkpoint(job_id, "test_pipeline", "step_1", {"data": 1})
    checkpoint_store.save_checkpoint(job_id, "test_pipeline", "step_2", {"data": 2})
    
    step, payload = checkpoint_store.load_checkpoint(job_id)
    assert step == "step_2"
    assert payload["data"] == 2

def test_checkpoint_mark_completed_sqlite(checkpoint_store):
    """Test marking a job as completed."""
    job_id = "test_job_3"
    checkpoint_store.save_checkpoint(job_id, "test_pipeline", "step_1", {})
    checkpoint_store.mark_completed(job_id)
    
    with checkpoint_store.db.get_connection() as conn:
        row = conn.execute("SELECT status FROM pipeline_checkpoints WHERE job_id = ?", (job_id,)).fetchone()
        assert row["status"] == "completed"
