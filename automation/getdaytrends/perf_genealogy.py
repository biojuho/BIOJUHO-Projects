"""
getdaytrends - Trend Genealogy Mixin

PerformanceTracker에서 분리된 트렌드 계보 추적 기능.
키워드 간 부모-자식 관계를 추적하여 트렌드 진화 패턴을 분석합니다.
"""

import json
from datetime import UTC, datetime, timedelta


class TrendGenealogyMixin:
    """[A] Trend Genealogy 관리 기능 (PerformanceTracker Mixin)."""

    def save_trend_genealogy(
        self,
        keyword: str,
        parent_keyword: str = "",
        predicted_children: list[str] | None = None,
        viral_score: int = 0,
    ) -> None:
        """[A] 트렌드 계보 저장/갱신."""
        self.init_table()
        conn = self._get_conn()
        now = datetime.now(UTC).isoformat()
        children_json = json.dumps(predicted_children or [], ensure_ascii=False)
        try:
            existing = conn.execute(
                "SELECT id, total_appearances, peak_viral_score FROM trend_genealogy WHERE keyword = ? AND parent_keyword = ?",
                (keyword, parent_keyword),
            ).fetchone()
            if existing:
                new_count = existing["total_appearances"] + 1
                new_peak = max(existing["peak_viral_score"], viral_score)
                conn.execute(
                    """UPDATE trend_genealogy
                       SET last_seen_at = ?, total_appearances = ?,
                           peak_viral_score = ?, predicted_children = ?
                       WHERE id = ?""",
                    (now, new_count, new_peak, children_json, existing["id"]),
                )
            else:
                depth = 0
                if parent_keyword:
                    parent = conn.execute(
                        "SELECT genealogy_depth FROM trend_genealogy WHERE keyword = ? LIMIT 1",
                        (parent_keyword,),
                    ).fetchone()
                    depth = (parent["genealogy_depth"] + 1) if parent else 1
                conn.execute(
                    """INSERT INTO trend_genealogy
                       (keyword, parent_keyword, predicted_children, genealogy_depth,
                        first_seen_at, last_seen_at, peak_viral_score)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (keyword, parent_keyword, children_json, depth, now, now, viral_score),
                )
            conn.commit()
        finally:
            conn.close()

    def get_trend_history(self, keyword: str, hours: int = 72) -> list[dict]:
        """[A] 최근 N시간 이내 트렌드 히스토리 (계보 연결)."""
        self.init_table()
        conn = self._get_conn()
        try:
            cutoff = (datetime.now(UTC) - timedelta(hours=hours)).isoformat()
            rows = conn.execute(
                """SELECT keyword, parent_keyword, predicted_children,
                          genealogy_depth, total_appearances, peak_viral_score,
                          first_seen_at, last_seen_at
                   FROM trend_genealogy
                   WHERE last_seen_at >= ?
                   ORDER BY last_seen_at DESC""",
                (cutoff,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_predicted_children(self, keyword: str) -> list[str]:
        """[A] 특정 트렌드의 예측된 파생 트렌드 목록."""
        self.init_table()
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT predicted_children FROM trend_genealogy WHERE keyword = ? ORDER BY last_seen_at DESC LIMIT 1",
                (keyword,),
            ).fetchone()
            if row and row["predicted_children"]:
                return json.loads(row["predicted_children"])
            return []
        finally:
            conn.close()
