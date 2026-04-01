"""
GetDayTrends Viral Model Calibrator

예측된 viral_potential 스코어와 실제 X 인게이지먼트 지표를 비교 분석하여
scoring 정확도를 측정하고, 상위/하위 패턴을 추출한다.

출력:
  - SQLite calibration_insights 테이블 갱신
  - data/calibration_report_<date>.json
  - 표준 출력 요약

실행:
  python scripts/calibrate_viral_model.py
  python scripts/calibrate_viral_model.py --lookback-days 30 --json-out data/cal.json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


# ── 상수 ─────────────────────────────────────────────────────────────────────

_TIER_THRESHOLDS = {
    "high": 80,   # viral_potential >= 80
    "mid": 60,    # 60 <= viral_potential < 80
    "low": 0,     # viral_potential < 60
}
_TOP_N = 20          # 상위/하위 샘플 패턴 추출 개수
_MIN_IMPRESSIONS = 5  # 유효 메트릭으로 간주할 최소 노출 수


# ── CLI ──────────────────────────────────────────────────────────────────────

def _parse_args(argv=None) -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    project_dir = script_dir.parent
    default_db = str(project_dir / "data" / "getdaytrends.db")

    parser = argparse.ArgumentParser(
        description="GetDayTrends viral score calibration analysis"
    )
    parser.add_argument("--db-path", default=default_db, help="SQLite DB 경로")
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=14,
        help="분석 기간 (일 단위, 기본 14일)",
    )
    parser.add_argument("--json-out", help="JSON 리포트 출력 경로")
    parser.add_argument(
        "--min-impressions",
        type=int,
        default=_MIN_IMPRESSIONS,
        help="유효 트윗으로 간주할 최소 노출 수",
    )
    return parser.parse_args(argv)


# ── DB helpers ───────────────────────────────────────────────────────────────

def _get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _ensure_calibration_table(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS calibration_insights (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            generated_at    TEXT NOT NULL,
            lookback_days   INTEGER NOT NULL,
            sample_count    INTEGER DEFAULT 0,

            -- 예측 정확도
            mae             REAL DEFAULT 0.0,
            pearson_r       REAL DEFAULT 0.0,
            tier_precision_high  REAL DEFAULT 0.0,
            tier_precision_mid   REAL DEFAULT 0.0,
            tier_precision_low   REAL DEFAULT 0.0,

            -- 최적 발행 시간
            best_hour_kst   INTEGER DEFAULT -1,
            best_hour_avg_eng REAL DEFAULT 0.0,

            -- 상위/하위 패턴 (JSON)
            top_keywords    TEXT DEFAULT '[]',
            bottom_keywords TEXT DEFAULT '[]',
            top_angles      TEXT DEFAULT '[]',
            bottom_angles   TEXT DEFAULT '[]',
            top_hooks       TEXT DEFAULT '[]',

            -- 추천 프롬프트 힌트 (JSON)
            prompt_hints    TEXT DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS idx_ci_generated ON calibration_insights(generated_at);
    """)
    conn.commit()


# ── 데이터 수집 ───────────────────────────────────────────────────────────────

def _fetch_paired_data(
    conn: sqlite3.Connection,
    since_iso: str,
    min_impressions: int,
) -> list[dict]:
    """
    trends.viral_potential + tweets 실제 성과를 조인.
    tweet_performance 테이블이 있으면 상세 메트릭(likes/retweets) 도 포함.
    """
    # tweet_performance 테이블 존재 여부 확인
    has_tp = bool(
        conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tweet_performance'"
        ).fetchone()
    )

    if has_tp:
        sql = """
            SELECT
                t.keyword,
                t.viral_potential          AS predicted_score,
                t.joongyeon_angle          AS angle,
                tw.content_type,
                tw.impressions,
                tw.engagements,
                tw.engagement_rate,
                tw.posted_at,
                tp.likes,
                tp.retweets,
                tp.replies,
                tp.angle_type              AS perf_angle,
                tp.hook_pattern
            FROM trends t
            JOIN tweets tw ON tw.trend_id = t.id
            LEFT JOIN tweet_performance tp ON tp.tweet_id = tw.x_tweet_id
            WHERE tw.posted_at IS NOT NULL
              AND tw.posted_at >= ?
              AND tw.x_tweet_id != ''
              AND tw.impressions >= ?
            ORDER BY tw.posted_at DESC
        """
    else:
        sql = """
            SELECT
                t.keyword,
                t.viral_potential          AS predicted_score,
                t.joongyeon_angle          AS angle,
                tw.content_type,
                tw.impressions,
                tw.engagements,
                tw.engagement_rate,
                tw.posted_at,
                NULL AS likes,
                NULL AS retweets,
                NULL AS replies,
                t.joongyeon_angle          AS perf_angle,
                t.best_hook_starter        AS hook_pattern
            FROM trends t
            JOIN tweets tw ON tw.trend_id = t.id
            WHERE tw.posted_at IS NOT NULL
              AND tw.posted_at >= ?
              AND tw.x_tweet_id != ''
              AND tw.impressions >= ?
            ORDER BY tw.posted_at DESC
        """

    rows = conn.execute(sql, (since_iso, min_impressions)).fetchall()
    return [dict(r) for r in rows]


# ── 분석 함수 ─────────────────────────────────────────────────────────────────

def _engagement_score(row: dict) -> float:
    """단일 인게이지먼트 점수 (0-100 정규화된 복합 지표)."""
    impr = row.get("impressions") or 1
    eng = row.get("engagements") or 0
    likes = row.get("likes") or 0
    rts = row.get("retweets") or 0
    replies = row.get("replies") or 0

    # 가중 합산: retweet(3x) > reply(2x) > like(1x) > raw engagements
    weighted = (likes * 1 + rts * 3 + replies * 2) if (likes or rts or replies) else eng
    rate = (weighted / impr) * 100
    # 0-100 클램프 (극단값 제거)
    return min(rate, 100.0)


def _assign_tier(score: float) -> str:
    if score >= _TIER_THRESHOLDS["high"]:
        return "high"
    if score >= _TIER_THRESHOLDS["mid"]:
        return "mid"
    return "low"


def _pearson(xs: list[float], ys: list[float]) -> float:
    """피어슨 상관계수 (표준 라이브러리만 사용)."""
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    denom = (
        (sum((x - mx) ** 2 for x in xs) ** 0.5)
        * (sum((y - my) ** 2 for y in ys) ** 0.5)
    )
    return round(num / denom, 4) if denom else 0.0


def _tier_precision(data: list[dict]) -> dict[str, float]:
    """
    예측 tier가 실제 인게이지먼트 tier와 일치하는 비율.
    실제 tier 기준: 상위 25% → high, 하위 25% → low, 나머지 → mid
    """
    if not data:
        return {"high": 0.0, "mid": 0.0, "low": 0.0}

    scores = sorted(r["_eng_score"] for r in data)
    n = len(scores)
    q75 = scores[int(n * 0.75)]
    q25 = scores[int(n * 0.25)]

    def _actual_tier(s: float) -> str:
        if s >= q75:
            return "high"
        if s <= q25:
            return "low"
        return "mid"

    per_tier: dict[str, list[bool]] = {"high": [], "mid": [], "low": []}
    for r in data:
        pred = _assign_tier(r["predicted_score"])
        actual = _actual_tier(r["_eng_score"])
        per_tier[pred].append(pred == actual)

    return {
        k: round(sum(v) / len(v), 4) if v else 0.0
        for k, v in per_tier.items()
    }


def _best_posting_hour(data: list[dict]) -> tuple[int, float]:
    """KST 기준 최고 평균 인게이지먼트 시간대."""
    hour_scores: dict[int, list[float]] = {}
    for r in data:
        posted_at = r.get("posted_at")
        if not posted_at:
            continue
        try:
            dt = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
            kst_hour = (dt.hour + 9) % 24
            hour_scores.setdefault(kst_hour, []).append(r["_eng_score"])
        except (ValueError, AttributeError):
            continue

    if not hour_scores:
        return -1, 0.0

    best_hour = max(hour_scores, key=lambda h: statistics.mean(hour_scores[h]))
    return best_hour, round(statistics.mean(hour_scores[best_hour]), 4)


def _top_bottom_keywords(data: list[dict], n: int) -> tuple[list[dict], list[dict]]:
    """인게이지먼트 기준 상위/하위 N 키워드 패턴."""
    by_keyword: dict[str, list[float]] = {}
    for r in data:
        kw = r.get("keyword", "")
        if kw:
            by_keyword.setdefault(kw, []).append(r["_eng_score"])

    ranked = sorted(
        [
            {
                "keyword": kw,
                "avg_eng": round(statistics.mean(scores), 2),
                "sample": len(scores),
            }
            for kw, scores in by_keyword.items()
        ],
        key=lambda x: x["avg_eng"],
        reverse=True,
    )
    return ranked[:n], ranked[-n:][::-1]


def _top_bottom_angles(data: list[dict], n: int) -> tuple[list[dict], list[dict]]:
    """각도(angle) 타입별 평균 인게이지먼트."""
    by_angle: dict[str, list[float]] = {}
    for r in data:
        angle = r.get("perf_angle") or r.get("angle") or "unknown"
        angle = angle.strip() or "unknown"
        by_angle.setdefault(angle, []).append(r["_eng_score"])

    ranked = sorted(
        [
            {
                "angle": ang,
                "avg_eng": round(statistics.mean(scores), 2),
                "sample": len(scores),
            }
            for ang, scores in by_angle.items()
        ],
        key=lambda x: x["avg_eng"],
        reverse=True,
    )
    return ranked[:n], ranked[-n:][::-1]


def _top_hooks(data: list[dict], n: int) -> list[dict]:
    """훅 패턴별 평균 인게이지먼트 상위 N."""
    by_hook: dict[str, list[float]] = {}
    for r in data:
        hook = r.get("hook_pattern") or "unknown"
        hook = hook.strip() or "unknown"
        by_hook.setdefault(hook, []).append(r["_eng_score"])

    return sorted(
        [
            {
                "hook": h,
                "avg_eng": round(statistics.mean(scores), 2),
                "sample": len(scores),
            }
            for h, scores in by_hook.items()
        ],
        key=lambda x: x["avg_eng"],
        reverse=True,
    )[:n]


def _build_prompt_hints(
    top_kw: list[dict],
    bottom_kw: list[dict],
    top_angles: list[dict],
    top_hooks: list[dict],
) -> dict:
    """
    생성 프롬프트에 주입할 힌트 딕셔너리.
    generator.py 또는 prompt_builder.py에서 직접 로드 가능한 포맷.
    """
    return {
        "prefer_keywords": [k["keyword"] for k in top_kw[:5]],
        "avoid_keywords": [k["keyword"] for k in bottom_kw[:5]],
        "prefer_angles": [a["angle"] for a in top_angles[:3]],
        "prefer_hooks": [h["hook"] for h in top_hooks[:3]],
        "calibrated_at": datetime.now(UTC).isoformat(),
    }


# ── 인사이트 저장 ─────────────────────────────────────────────────────────────

def _save_insights(
    conn: sqlite3.Connection,
    generated_at: str,
    lookback_days: int,
    report: dict,
) -> None:
    conn.execute(
        """
        INSERT INTO calibration_insights (
            generated_at, lookback_days, sample_count,
            mae, pearson_r,
            tier_precision_high, tier_precision_mid, tier_precision_low,
            best_hour_kst, best_hour_avg_eng,
            top_keywords, bottom_keywords,
            top_angles, bottom_angles, top_hooks,
            prompt_hints
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            generated_at,
            lookback_days,
            report["sample_count"],
            report["accuracy"]["mae"],
            report["accuracy"]["pearson_r"],
            report["accuracy"]["tier_precision"]["high"],
            report["accuracy"]["tier_precision"]["mid"],
            report["accuracy"]["tier_precision"]["low"],
            report["posting_time"]["best_hour_kst"],
            report["posting_time"]["best_hour_avg_eng"],
            json.dumps(report["patterns"]["top_keywords"], ensure_ascii=False),
            json.dumps(report["patterns"]["bottom_keywords"], ensure_ascii=False),
            json.dumps(report["patterns"]["top_angles"], ensure_ascii=False),
            json.dumps(report["patterns"]["bottom_angles"], ensure_ascii=False),
            json.dumps(report["patterns"]["top_hooks"], ensure_ascii=False),
            json.dumps(report["prompt_hints"], ensure_ascii=False),
        ),
    )
    conn.commit()


# ── 메인 ─────────────────────────────────────────────────────────────────────

def run(db_path: str, lookback_days: int, min_impressions: int) -> dict[str, Any]:
    since = (datetime.now(UTC) - timedelta(days=lookback_days)).isoformat()
    conn = _get_conn(db_path)
    _ensure_calibration_table(conn)

    data = _fetch_paired_data(conn, since, min_impressions)
    if not data:
        return {
            "status": "no_data",
            "message": f"유효 트윗 없음 (lookback={lookback_days}d, min_impressions={min_impressions})",
        }

    # 인게이지먼트 복합 점수 계산
    for r in data:
        r["_eng_score"] = _engagement_score(r)

    predicted = [float(r["predicted_score"]) for r in data]
    actual = [r["_eng_score"] for r in data]

    # MAE: 예측 viral_potential과 실제 eng_score의 평균 절대 오차
    mae = round(
        statistics.mean(abs(p - a) for p, a in zip(predicted, actual)), 4
    )
    pearson_r = _pearson(predicted, actual)
    tier_prec = _tier_precision(data)
    best_hour, best_hour_eng = _best_posting_hour(data)

    top_kw, bottom_kw = _top_bottom_keywords(data, _TOP_N)
    top_ang, bottom_ang = _top_bottom_angles(data, _TOP_N)
    top_hooks = _top_hooks(data, _TOP_N)
    prompt_hints = _build_prompt_hints(top_kw, bottom_kw, top_ang, top_hooks)

    generated_at = datetime.now(UTC).isoformat()

    report: dict[str, Any] = {
        "generated_at": generated_at,
        "lookback_days": lookback_days,
        "sample_count": len(data),
        "accuracy": {
            "mae": mae,
            "pearson_r": pearson_r,
            "tier_precision": tier_prec,
            "interpretation": _interpret_accuracy(pearson_r, tier_prec),
        },
        "posting_time": {
            "best_hour_kst": best_hour,
            "best_hour_avg_eng": best_hour_eng,
        },
        "patterns": {
            "top_keywords": top_kw,
            "bottom_keywords": bottom_kw,
            "top_angles": top_ang,
            "bottom_angles": bottom_ang,
            "top_hooks": top_hooks,
        },
        "prompt_hints": prompt_hints,
    }

    _save_insights(conn, generated_at, lookback_days, report)
    conn.close()
    return report


def _interpret_accuracy(pearson_r: float, tier_prec: dict) -> str:
    """사람이 읽기 쉬운 정확도 해석."""
    avg_prec = statistics.mean(tier_prec.values())
    if pearson_r >= 0.6 and avg_prec >= 0.7:
        return "excellent - 모델이 실제 성과를 잘 예측하고 있습니다"
    if pearson_r >= 0.4 or avg_prec >= 0.55:
        return "moderate - 방향성은 맞지만 스코어 보정 필요"
    return "weak - 프롬프트 재조정 권장 (prompt_hints 적용)"


def _print_summary(report: dict) -> None:
    if report.get("status") == "no_data":
        print(f"[경고] {report['message']}")
        return

    acc = report["accuracy"]
    pt = report["posting_time"]
    hints = report["prompt_hints"]

    print("\n" + "=" * 56)
    print("  GetDayTrends Viral Model Calibration Report")
    print("=" * 56)
    print(f"  기간        : 최근 {report['lookback_days']}일  |  샘플 {report['sample_count']}건")
    print(f"  MAE         : {acc['mae']:.2f}  (예측-실제 평균 오차)")
    print(f"  Pearson r   : {acc['pearson_r']:.4f}")
    print(f"  Tier 정확도 : high={acc['tier_precision']['high']:.0%}  mid={acc['tier_precision']['mid']:.0%}  low={acc['tier_precision']['low']:.0%}")
    print(f"  평가        : {acc['interpretation']}")
    print(f"  최적 발행 KST: {pt['best_hour_kst']:02d}:00  (평균 eng {pt['best_hour_avg_eng']:.2f})")
    print()
    print("  [상위 키워드]", "  /  ".join(hints["prefer_keywords"]))
    print("  [회피 키워드]", "  /  ".join(hints["avoid_keywords"]))
    print("  [상위 앵글] ", "  /  ".join(hints["prefer_angles"]))
    print("  [상위 훅]   ", "  /  ".join(hints["prefer_hooks"]))
    print("=" * 56 + "\n")


# ── 엔트리포인트 ──────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    args = _parse_args(argv)

    if not Path(args.db_path).exists():
        print(f"DB 파일 없음: {args.db_path}")
        return 1

    report = run(
        db_path=args.db_path,
        lookback_days=args.lookback_days,
        min_impressions=args.min_impressions,
    )

    _print_summary(report)

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"json_out: {out.resolve()}")

    # 기본 날짜 기반 리포트 저장
    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    script_dir = Path(__file__).resolve().parent
    default_out = script_dir.parent / "data" / f"calibration_report_{date_str}.json"
    if not args.json_out:
        default_out.parent.mkdir(parents=True, exist_ok=True)
        default_out.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"json_out: {default_out.resolve()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
