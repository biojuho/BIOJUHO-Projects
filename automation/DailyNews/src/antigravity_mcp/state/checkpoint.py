"""Idempotency Checkpoint Store for Pipeline State Recovery."""
from __future__ import annotations

import json
import logging
from typing import Any

from antigravity_mcp.state.db_client import CheckpointDBClient

logger = logging.getLogger(__name__)


class CheckpointStore:
    """Manages idempotent checkpoints for pipelines."""
    
    def __init__(self) -> None:
        self.db = CheckpointDBClient()

    def close(self) -> None:
        self.db.close()

    def save_checkpoint(self, job_id: str, pipeline_name: str, step: str, state_payload: dict[str, Any]) -> None:
        """Save a checkpoint at a specific step in the pipeline."""
        payload_str = json.dumps(state_payload, ensure_ascii=False)
        
        with self.db.get_connection() as conn:
            if self.db.use_postgres:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO pipeline_checkpoints (job_id, pipeline_name, current_step, state_json, status, updated_at)
                        VALUES (%s, %s, %s, %s, 'running', NOW())
                        ON CONFLICT (job_id) DO UPDATE SET 
                            current_step = EXCLUDED.current_step,
                            state_json = EXCLUDED.state_json,
                            status = 'running',
                            updated_at = NOW()
                    """, (job_id, pipeline_name, step, payload_str))
                conn.commit()
            else:
                conn.execute("""
                    INSERT INTO pipeline_checkpoints (job_id, pipeline_name, current_step, state_json, status, updated_at)
                    VALUES (?, ?, ?, ?, 'running', CURRENT_TIMESTAMP)
                    ON CONFLICT (job_id) DO UPDATE SET 
                        current_step = excluded.current_step,
                        state_json = excluded.state_json,
                        status = 'running',
                        updated_at = CURRENT_TIMESTAMP
                """, (job_id, pipeline_name, step, payload_str))
                conn.commit()
                
        logger.info(f"Pipeline Checkpoint saved: [{pipeline_name}] job='{job_id}' step='{step}'")

    def load_checkpoint(self, job_id: str) -> tuple[str | None, dict[str, Any]]:
        """Load the last checkpoint state for a given job. Returns (step, payload)."""
        with self.db.get_connection() as conn:
            if self.db.use_postgres:
                with conn.cursor() as cur:
                    cur.execute("SELECT current_step, state_json FROM pipeline_checkpoints WHERE job_id = %s", (job_id,))
                    row = cur.fetchone()
            else:
                row = conn.execute("SELECT current_step, state_json FROM pipeline_checkpoints WHERE job_id = ?", (job_id,)).fetchone()
                
        if not row:
            return None, {}
            
        step = row["current_step"]
        # PostgreSQL JSONB returns literal dict if RealDictCursor handles it, or string if raw. SQLite returns string.
        state_raw = row["state_json"]
        if isinstance(state_raw, str):
            state_data = json.loads(state_raw)
        else:
            state_data = state_raw
            
        return step, state_data

    def mark_completed(self, job_id: str) -> None:
        """Mark a job as completely finished."""
        with self.db.get_connection() as conn:
            if self.db.use_postgres:
                with conn.cursor() as cur:
                    cur.execute("UPDATE pipeline_checkpoints SET status = 'completed', updated_at = NOW() WHERE job_id = %s", (job_id,))
                conn.commit()
            else:
                conn.execute("UPDATE pipeline_checkpoints SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE job_id = ?", (job_id,))
                conn.commit()
        logger.info(f"Pipeline Checkpoint marked completed: job='{job_id}'")
