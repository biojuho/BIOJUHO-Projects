from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

DEFAULT_LLM_WEIGHT = 0.6
DEFAULT_MIN_CONFIDENCE = 2
DEFAULT_LOW_CONFIDENCE_PENALTY = 0.65


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    project_dir = script_dir.parent
    parser = argparse.ArgumentParser(
        description="Export a historical GetDayTrends dataset for viral scoring A/B evaluation."
    )
    parser.add_argument(
        "--db-path",
        default=str(project_dir / "data" / "getdaytrends.db"),
        help="Path to the GetDayTrends SQLite database.",
    )
    parser.add_argument(
        "--lookahead-hours",
        type=int,
        default=48,
        help="Future window used to infer whether a trend became a sustained hit.",
    )
    parser.add_argument(
        "--min-relative-future-score",
        type=float,
        default=0.8,
        help="Minimum fraction of the initial score required for a future recurrence to count as a hit.",
    )
    parser.add_argument(
        "--label-mode",
        choices=("auto", "measured", "inferred"),
        default="auto",
        help="Use measured X performance labels when available, inferred recurrence labels, or auto-select between them.",
    )
    parser.add_argument(
        "--min-actual-impressions",
        type=int,
        default=100,
        help="Minimum measured impressions required before a posted tweet can be used as a real outcome label.",
    )
    parser.add_argument(
        "--min-actual-engagement-rate",
        type=float,
        default=0.03,
        help="Minimum measured engagement rate required for a real-performance hit label.",
    )
    parser.add_argument(
        "--output",
        default=str(project_dir / "data" / "ab_tests" / "viral_scoring_history.json"),
        help="Output JSON path.",
    )
    return parser.parse_args()


def estimate_single_source_score(
    multi_source_score: int,
    cross_source_confidence: int,
    *,
    llm_weight: float = DEFAULT_LLM_WEIGHT,
    min_confidence: int = DEFAULT_MIN_CONFIDENCE,
    low_confidence_penalty: float = DEFAULT_LOW_CONFIDENCE_PENALTY,
) -> float:
    source_bonus = min(cross_source_confidence * 5.0, 20.0) * (1.0 - llm_weight)
    baseline = float(multi_source_score)

    # Reverse the low-confidence penalty before stripping corroboration bonus.
    if cross_source_confidence < min_confidence and baseline > 0:
        baseline = baseline / low_confidence_penalty

    return round(max(0.0, min(100.0, baseline - source_bonus)), 1)


def fetch_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    query = """
    SELECT tr.id,
           tr.run_id,
           tr.keyword,
           tr.rank,
           tr.volume_numeric,
           tr.viral_potential,
           tr.cross_source_confidence,
           tr.scored_at,
           COUNT(tw.id) AS tweet_count,
           SUM(CASE WHEN tw.posted_at IS NOT NULL AND tw.posted_at != '' THEN 1 ELSE 0 END) AS posted_tweet_count,
           MAX(COALESCE(tw.impressions, 0)) AS max_impressions,
           AVG(CASE WHEN COALESCE(tw.impressions, 0) > 0 THEN tw.impressions END) AS avg_impressions,
           MAX(COALESCE(tw.engagement_rate, 0.0)) AS max_engagement_rate,
           AVG(CASE WHEN COALESCE(tw.impressions, 0) > 0 THEN tw.engagement_rate END) AS avg_engagement_rate
    FROM trends tr
    LEFT JOIN tweets tw ON tw.trend_id = tr.id
    GROUP BY tr.id
    ORDER BY tr.scored_at ASC, tr.id ASC
    """
    return conn.execute(query).fetchall()


def resolve_actual_hit(
    row: sqlite3.Row,
    *,
    label_mode: str,
    min_actual_impressions: int,
    min_actual_engagement_rate: float,
    inferred_hit: bool,
) -> tuple[bool, str]:
    posted_tweet_count = int(row["posted_tweet_count"] or 0)
    max_impressions = int(row["max_impressions"] or 0)
    max_engagement_rate = float(row["max_engagement_rate"] or 0.0)

    measured_ready = posted_tweet_count > 0 and max_impressions >= min_actual_impressions
    measured_hit = measured_ready and max_engagement_rate >= min_actual_engagement_rate

    if label_mode == "measured":
        return measured_hit, "measured_x_performance" if measured_ready else "pending_measured_x_performance"

    if label_mode == "inferred":
        return inferred_hit, "inferred_recurrence"

    if measured_ready:
        return measured_hit, "measured_x_performance"

    return inferred_hit, "inferred_recurrence"


def build_observations(
    rows: list[sqlite3.Row],
    *,
    lookahead_hours: int,
    min_relative_future_score: float,
    label_mode: str,
    min_actual_impressions: int,
    min_actual_engagement_rate: float,
) -> tuple[list[dict], dict]:
    by_keyword: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        by_keyword[row["keyword"]].append(row)

    latest_scored_at = max(datetime.fromisoformat(row["scored_at"]) for row in rows)
    cutoff = latest_scored_at - timedelta(hours=lookahead_hours)
    observations: list[dict] = []
    skipped_incomplete = 0
    measured_labels = 0
    inferred_labels = 0
    pending_measured_labels = 0

    for keyword, items in by_keyword.items():
        first = items[0]
        first_dt = datetime.fromisoformat(first["scored_at"])
        if first_dt > cutoff:
            skipped_incomplete += 1
            continue

        future_items = [
            item
            for item in items[1:]
            if first_dt < datetime.fromisoformat(item["scored_at"]) <= first_dt + timedelta(hours=lookahead_hours)
        ]
        future_scores = [item["viral_potential"] for item in future_items]
        future_threshold = round(first["viral_potential"] * min_relative_future_score, 1)
        inferred_hit = any(score >= future_threshold for score in future_scores)
        actual_hit, actual_hit_source = resolve_actual_hit(
            first,
            label_mode=label_mode,
            min_actual_impressions=min_actual_impressions,
            min_actual_engagement_rate=min_actual_engagement_rate,
            inferred_hit=inferred_hit,
        )

        if actual_hit_source == "measured_x_performance":
            measured_labels += 1
        elif actual_hit_source == "pending_measured_x_performance":
            pending_measured_labels += 1
        else:
            inferred_labels += 1

        observations.append(
            {
                "keyword": keyword,
                "trend_id": first["id"],
                "run_id": first["run_id"],
                "scored_at": first["scored_at"],
                "rank": first["rank"],
                "volume_numeric": first["volume_numeric"],
                "cross_source_confidence": first["cross_source_confidence"],
                "tweet_count": first["tweet_count"],
                "posted_tweet_count": int(first["posted_tweet_count"] or 0),
                "single_source_score": estimate_single_source_score(
                    first["viral_potential"], first["cross_source_confidence"]
                ),
                "multi_source_score": float(first["viral_potential"]),
                "actual_hit": actual_hit,
                "actual_hit_source": actual_hit_source,
                "measured_impressions": int(first["max_impressions"] or 0),
                "measured_avg_impressions": round(float(first["avg_impressions"] or 0.0), 1),
                "measured_engagement_rate": round(float(first["max_engagement_rate"] or 0.0), 6),
                "measured_avg_engagement_rate": round(float(first["avg_engagement_rate"] or 0.0), 6),
                "future_appearances": len(future_items),
                "future_max_score": max(future_scores) if future_scores else 0,
                "future_threshold": future_threshold,
                "notes": (
                    "single_source_score is a proxy derived from stored viral_potential by "
                    "removing corroboration bonus and reversing low-confidence penalty. "
                    "actual_hit_source indicates whether the label came from measured X performance "
                    "or fallback recurrence inference."
                ),
            }
        )

    observations.sort(
        key=lambda item: (
            item["scored_at"],
            -item["multi_source_score"],
            item["keyword"],
        )
    )
    summary = {
        "latest_scored_at": latest_scored_at.isoformat(),
        "skipped_incomplete_keywords": skipped_incomplete,
        "positive_labels": sum(1 for item in observations if item["actual_hit"]),
        "negative_labels": sum(1 for item in observations if not item["actual_hit"]),
        "measured_labels": measured_labels,
        "inferred_labels": inferred_labels,
        "pending_measured_labels": pending_measured_labels,
    }
    return observations, summary


def write_json(path_str: str, payload: dict) -> Path:
    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def main() -> int:
    args = parse_args()
    db_path = Path(args.db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = fetch_rows(conn)
    finally:
        conn.close()

    observations, summary = build_observations(
        rows,
        lookahead_hours=args.lookahead_hours,
        min_relative_future_score=args.min_relative_future_score,
        label_mode=args.label_mode,
        min_actual_impressions=args.min_actual_impressions,
        min_actual_engagement_rate=args.min_actual_engagement_rate,
    )

    payload = {
        "dataset_name": "getdaytrends historical viral scoring dataset",
        "metadata": {
            "exported_at": datetime.now(UTC).astimezone().isoformat(),
            "source_db": str(db_path.resolve()),
            "observation_mode": "first keyword appearance with full future window",
            "lookahead_hours": args.lookahead_hours,
            "label_mode": args.label_mode,
            "label_method": (
                "actual_hit uses measured X engagement when posted tweets have enough impressions; "
                "otherwise it falls back to recurrence inference unless label_mode forces a single strategy"
            ),
            "score_method": (
                "multi_source_score uses stored viral_potential; single_source_score is "
                "a proxy derived from analysis/parsing.py weighting assumptions"
            ),
            "min_relative_future_score": args.min_relative_future_score,
            "min_actual_impressions": args.min_actual_impressions,
            "min_actual_engagement_rate": args.min_actual_engagement_rate,
            "total_trend_rows": len(rows),
            "total_observations": len(observations),
            **summary,
        },
        "observations": observations,
    }
    output_path = write_json(args.output, payload)

    print(f"exported {len(observations)} observations")
    print(f"positive labels: {summary['positive_labels']}")
    print(f"negative labels: {summary['negative_labels']}")
    print(f"output: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
