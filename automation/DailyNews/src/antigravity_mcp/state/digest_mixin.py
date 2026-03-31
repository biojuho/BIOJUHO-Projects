"""Mixin for Digest queue management.

Follows the same pattern as existing mixins in :pymod:`antigravity_mcp.state.mixins`.
"""

from __future__ import annotations

import json

from antigravity_mcp.domain.models import DigestEntry
from antigravity_mcp.state.base import _DBProviderBase
from antigravity_mcp.state.events import utc_now_iso


class _DigestMixin(_DBProviderBase):
    """CRUD for the ``digest_queue`` table."""

    def enqueue_for_digest(self, report_id: str) -> None:
        """Add a report to the digest queue with 'pending' status."""
        now = utc_now_iso()
        with self._connect() as conn:
            # Check if already queued
            existing = conn.execute(
                "SELECT digest_id, report_ids_json FROM digest_queue WHERE status = 'pending' ORDER BY created_at DESC LIMIT 1",
            ).fetchone()

            if existing:
                report_ids = json.loads(existing["report_ids_json"] or "[]")
                if report_id not in report_ids:
                    report_ids.append(report_id)
                    conn.execute(
                        "UPDATE digest_queue SET report_ids_json = ? WHERE digest_id = ?",
                        (json.dumps(report_ids, ensure_ascii=False), existing["digest_id"]),
                    )
            else:
                import hashlib

                digest_id = hashlib.sha256(f"digest-{now}".encode()).hexdigest()[:16]
                conn.execute(
                    """
                    INSERT INTO digest_queue
                        (digest_id, report_ids_json, summary_text, serial_number, status, created_at)
                    VALUES (?, ?, '', '', 'pending', ?)
                    """,
                    (digest_id, json.dumps([report_id], ensure_ascii=False), now),
                )

    def get_digest_queue(self, status: str = "pending") -> list[DigestEntry]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM digest_queue WHERE status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        return [
            DigestEntry(
                digest_id=r["digest_id"],
                report_ids=json.loads(r["report_ids_json"] or "[]"),
                summary_text=r["summary_text"],
                serial_number=r["serial_number"],
                status=r["status"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def save_digest(self, digest: DigestEntry) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO digest_queue
                    (digest_id, report_ids_json, summary_text, serial_number, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    digest.digest_id,
                    json.dumps(digest.report_ids, ensure_ascii=False),
                    digest.summary_text,
                    digest.serial_number,
                    digest.status,
                    digest.created_at or utc_now_iso(),
                ),
            )

    def get_next_serial_number(self) -> str:
        """Generate the next digest serial number in '0001_YYMMDD' format."""
        from datetime import date

        today = date.today()
        date_part = today.strftime("%y%m%d")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM digest_queue WHERE serial_number LIKE ?",
                (f"%_{date_part}",),
            ).fetchone()
        seq = (row["cnt"] or 0) + 1
        return f"{seq:04d}_{date_part}"
