"""
Content ROI Intelligence Report

LLM 비용과 실제 X 인게이지먼트를 조합하여 콘텐츠 ROI를 분석한다.

분석 항목:
  - 트윗 1건당 LLM 비용
  - 키워드/카테고리별 ROI ($1당 인게이지먼트)
  - 최적 발행 시간대 히트맵 (KST)
  - 바이럴 예측 정확도 추이 (calibration_insights 참조)
  - Notion 주간 리포트 자동 발행 (NOTION_TOKEN 설정 시)

실행:
  python ops/scripts/roi_report.py
  python ops/scripts/roi_report.py --lookback-days 7 --no-notion
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import statistics
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


# ── 경로 설정 ─────────────────────────────────────────────────────────────────

_ROOT = Path(__file__).resolve().parents[2]
_GDT_DB = _ROOT / "automation" / "getdaytrends" / "data" / "getdaytrends.db"
_LLM_DB = _ROOT / "packages" / "shared" / "llm" / "data" / "llm_costs.db"
_OUT_DIR = _ROOT / "var" / "reports"


# ── CLI ──────────────────────────────────────────────────────────────────────

def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Content ROI Intelligence Report")
    parser.add_argument("--lookback-days", type=int, default=7, help="분석 기간 (기본 7일)")
    parser.add_argument(
        "--gdt-db", default=str(_GDT_DB), help="GetDayTrends SQLite DB 경로"
    )
    parser.add_argument(
        "--llm-db", default=str(_LLM_DB), help="LLM 비용 SQLite DB 경로"
    )
    parser.add_argument("--json-out", help="JSON 출력 경로 (기본: var/reports/roi_<date>.json)")
    parser.add_argument(
        "--no-notion", action="store_true", help="Notion 발행 건너뜀"
    )
    return parser.parse_args(argv)


# ── DB helpers ───────────────────────────────────────────────────────────────

def _conn(path: str) -> sqlite3.Connection:
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


# ── LLM 비용 수집 ─────────────────────────────────────────────────────────────

def _fetch_llm_costs(llm_db: str, since_iso: str) -> dict[str, Any]:
    """getdaytrends 프로젝트 LLM 비용 집계."""
    if not Path(llm_db).exists():
        return {"total_usd": 0.0, "calls": 0, "by_model": {}, "by_tier": {}}

    conn = _conn(llm_db)
    rows = conn.execute(
        """
        SELECT model, tier, cost_usd, success, timestamp
        FROM llm_calls
        WHERE timestamp >= ?
          AND (project = 'getdaytrends' OR project = '' OR project IS NULL)
        """,
        (since_iso,),
    ).fetchall()
    conn.close()

    total = 0.0
    calls = 0
    by_model: dict[str, float] = defaultdict(float)
    by_tier: dict[str, float] = defaultdict(float)

    for r in rows:
        cost = r["cost_usd"] or 0.0
        total += cost
        calls += 1
        by_model[r["model"]] += cost
        by_tier[r["tier"] or "unknown"] += cost

    return {
        "total_usd": round(total, 6),
        "calls": calls,
        "by_model": {k: round(v, 6) for k, v in by_model.items()},
        "by_tier": {k: round(v, 6) for k, v in by_tier.items()},
    }


# ── 트윗 성과 수집 ────────────────────────────────────────────────────────────

def _fetch_tweet_performance(gdt_db: str, since_iso: str) -> list[dict]:
    if not Path(gdt_db).exists():
        return []

    conn = _conn(gdt_db)

    # tweet_performance 테이블 존재 여부
    has_tp = bool(
        conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tweet_performance'"
        ).fetchone()
    )

    if has_tp:
        sql = """
            SELECT
                t.keyword,
                t.viral_potential      AS predicted_score,
                t.joongyeon_angle      AS angle,
                tw.content_type,
                tw.impressions,
                tw.engagements,
                tw.engagement_rate,
                tw.posted_at,
                tp.likes,
                tp.retweets,
                tp.replies
            FROM trends t
            JOIN tweets tw ON tw.trend_id = t.id
            LEFT JOIN tweet_performance tp ON tp.tweet_id = tw.x_tweet_id
            WHERE tw.posted_at >= ?
              AND tw.x_tweet_id != ''
            ORDER BY tw.posted_at DESC
        """
    else:
        sql = """
            SELECT
                t.keyword,
                t.viral_potential      AS predicted_score,
                t.joongyeon_angle      AS angle,
                tw.content_type,
                tw.impressions,
                tw.engagements,
                tw.engagement_rate,
                tw.posted_at,
                NULL AS likes,
                NULL AS retweets,
                NULL AS replies
            FROM trends t
            JOIN tweets tw ON tw.trend_id = t.id
            WHERE tw.posted_at >= ?
              AND tw.x_tweet_id != ''
            ORDER BY tw.posted_at DESC
        """

    rows = conn.execute(sql, (since_iso,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _fetch_calibration_trend(gdt_db: str, limit: int = 8) -> list[dict]:
    """최근 calibration_insights 정확도 추이."""
    if not Path(gdt_db).exists():
        return []
    conn = _conn(gdt_db)
    has_table = bool(
        conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='calibration_insights'"
        ).fetchone()
    )
    if not has_table:
        conn.close()
        return []
    rows = conn.execute(
        """
        SELECT generated_at, pearson_r, mae, tier_precision_high,
               best_hour_kst, best_hour_avg_eng
        FROM calibration_insights
        ORDER BY generated_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── 분석 ──────────────────────────────────────────────────────────────────────

def _weighted_engagement(row: dict) -> float:
    impr = row.get("impressions") or 1
    likes = row.get("likes") or 0
    rts = row.get("retweets") or 0
    replies = row.get("replies") or 0
    eng = row.get("engagements") or 0
    weighted = (likes + rts * 3 + replies * 2) if (likes or rts or replies) else eng
    return (weighted / impr) * 100


def _roi_per_dollar(total_eng: float, total_cost: float) -> float:
    if total_cost <= 0:
        return 0.0
    return round(total_eng / total_cost, 2)


def _posting_time_heatmap(tweets: list[dict]) -> dict[int, dict]:
    """KST 시간대별 평균 인게이지먼트."""
    hourly: dict[int, list[float]] = defaultdict(list)
    for t in tweets:
        posted = t.get("posted_at")
        if not posted:
            continue
        try:
            dt = datetime.fromisoformat(posted.replace("Z", "+00:00"))
            kst_h = (dt.hour + 9) % 24
            hourly[kst_h].append(_weighted_engagement(t))
        except (ValueError, AttributeError):
            continue

    return {
        h: {
            "avg_eng": round(statistics.mean(scores), 4),
            "count": len(scores),
        }
        for h, scores in hourly.items()
    }


def _keyword_roi(tweets: list[dict], cost_per_tweet: float) -> list[dict]:
    """키워드별 평균 ROI."""
    by_kw: dict[str, list[float]] = defaultdict(list)
    for t in tweets:
        kw = t.get("keyword", "")
        if kw:
            by_kw[kw].append(_weighted_engagement(t))

    result = []
    for kw, engs in by_kw.items():
        avg_eng = statistics.mean(engs)
        result.append({
            "keyword": kw,
            "avg_eng": round(avg_eng, 3),
            "sample": len(engs),
            "roi_per_usd": _roi_per_dollar(avg_eng, cost_per_tweet) if cost_per_tweet > 0 else None,
        })

    return sorted(result, key=lambda x: x["avg_eng"], reverse=True)


def _content_type_breakdown(tweets: list[dict]) -> dict[str, dict]:
    """콘텐츠 유형별 성과."""
    by_type: dict[str, list[float]] = defaultdict(list)
    for t in tweets:
        ct = t.get("content_type") or "unknown"
        by_type[ct].append(_weighted_engagement(t))

    return {
        ct: {
            "avg_eng": round(statistics.mean(engs), 3),
            "count": len(engs),
        }
        for ct, engs in by_type.items()
    }


# ── 리포트 조립 ───────────────────────────────────────────────────────────────

def run(
    gdt_db: str,
    llm_db: str,
    lookback_days: int,
) -> dict[str, Any]:
    since = (datetime.now(UTC) - timedelta(days=lookback_days)).isoformat()

    llm = _fetch_llm_costs(llm_db, since)
    tweets = _fetch_tweet_performance(gdt_db, since)
    cal_trend = _fetch_calibration_trend(gdt_db)

    tweet_count = len(tweets)
    cost_per_tweet = (llm["total_usd"] / tweet_count) if tweet_count > 0 else 0.0

    all_engs = [_weighted_engagement(t) for t in tweets]
    total_eng = sum(all_engs)
    avg_eng = round(statistics.mean(all_engs), 4) if all_engs else 0.0

    heatmap = _posting_time_heatmap(tweets)
    best_hour = (
        max(heatmap, key=lambda h: heatmap[h]["avg_eng"])
        if heatmap else -1
    )

    kw_roi = _keyword_roi(tweets, cost_per_tweet)
    ct_breakdown = _content_type_breakdown(tweets)

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "lookback_days": lookback_days,
        "tweet_count": tweet_count,
        "llm_cost": llm,
        "cost_per_tweet_usd": round(cost_per_tweet, 6),
        "engagement": {
            "total": round(total_eng, 2),
            "avg_per_tweet": avg_eng,
            "roi_per_usd": _roi_per_dollar(total_eng, llm["total_usd"]),
        },
        "posting_time": {
            "heatmap_kst": heatmap,
            "best_hour_kst": best_hour,
            "best_hour_avg_eng": heatmap.get(best_hour, {}).get("avg_eng", 0.0),
        },
        "keyword_roi": kw_roi[:20],
        "content_type_breakdown": ct_breakdown,
        "calibration_trend": cal_trend,
    }


# ── 출력 ──────────────────────────────────────────────────────────────────────

def _print_summary(report: dict) -> None:
    llm = report["llm_cost"]
    eng = report["engagement"]
    pt = report["posting_time"]

    print("\n" + "=" * 60)
    print("  Content ROI Intelligence Report")
    print("=" * 60)
    print(f"  기간        : 최근 {report['lookback_days']}일  |  트윗 {report['tweet_count']}건")
    print(f"  LLM 비용    : ${llm['total_usd']:.4f}  ({llm['calls']}회 호출)")
    print(f"  트윗당 비용 : ${report['cost_per_tweet_usd']:.6f}")
    print(f"  총 인게이지 : {eng['total']:.1f}  (평균 {eng['avg_per_tweet']:.3f})")
    print(f"  ROI         : $1 → 인게이지먼트 {eng['roi_per_usd']:.1f}")
    print(f"  최적 발행   : KST {pt['best_hour_kst']:02d}:00  (평균 eng {pt['best_hour_avg_eng']:.3f})")
    print()

    if report["keyword_roi"]:
        print("  [Top 5 키워드 ROI]")
        for r in report["keyword_roi"][:5]:
            roi_str = f"  ROI/$ {r['roi_per_usd']:.1f}" if r["roi_per_usd"] else ""
            print(f"    {r['keyword']:<20} avg_eng={r['avg_eng']:.3f}  n={r['sample']}{roi_str}")
    print()

    if report["content_type_breakdown"]:
        print("  [콘텐츠 유형별 성과]")
        for ct, stats in sorted(
            report["content_type_breakdown"].items(),
            key=lambda x: x[1]["avg_eng"],
            reverse=True,
        ):
            print(f"    {ct:<12} avg_eng={stats['avg_eng']:.3f}  n={stats['count']}")
    print()

    cal = report["calibration_trend"]
    if cal:
        latest = cal[0]
        print(f"  [최신 Calibration] r={latest['pearson_r']:.4f}  MAE={latest['mae']:.2f}"
              f"  최적시간 KST {latest['best_hour_kst']:02d}:00")
    print("=" * 60 + "\n")


def _notion_blocks(report: dict) -> list[dict]:
    """Notion API blocks for the weekly report page."""
    eng = report["engagement"]
    llm = report["llm_cost"]
    pt = report["posting_time"]
    date_str = datetime.now(UTC).strftime("%Y-%m-%d")

    def _h2(text: str) -> dict:
        return {"object": "block", "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": text}}]}}

    def _para(text: str) -> dict:
        return {"object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}}]}}

    def _bul(text: str) -> dict:
        return {"object": "block", "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": text}}]}}

    blocks = [
        _h2(f"📊 GetDayTrends ROI 리포트 ({date_str})"),
        _para(f"기간: 최근 {report['lookback_days']}일  |  트윗 {report['tweet_count']}건 분석"),
        _h2("💰 비용 & ROI"),
        _bul(f"LLM 총비용: ${llm['total_usd']:.4f}  ({llm['calls']}회 호출)"),
        _bul(f"트윗 1건당 비용: ${report['cost_per_tweet_usd']:.6f}"),
        _bul(f"총 인게이지먼트: {eng['total']:.1f}  (트윗 평균 {eng['avg_per_tweet']:.3f})"),
        _bul(f"ROI: $1 → 인게이지먼트 {eng['roi_per_usd']:.1f}"),
        _h2("⏰ 최적 발행 시간"),
        _bul(f"KST {pt['best_hour_kst']:02d}:00  (평균 eng {pt['best_hour_avg_eng']:.3f})"),
        _h2("🏆 Top 5 키워드 ROI"),
    ]

    for r in report["keyword_roi"][:5]:
        roi_str = f"  ROI/$ {r['roi_per_usd']:.1f}" if r["roi_per_usd"] else ""
        blocks.append(_bul(f"{r['keyword']} - avg_eng {r['avg_eng']:.3f}  n={r['sample']}{roi_str}"))

    if report["calibration_trend"]:
        latest = report["calibration_trend"][0]
        blocks += [
            _h2("🎯 바이럴 모델 정확도"),
            _bul(f"Pearson r: {latest['pearson_r']:.4f}"),
            _bul(f"MAE: {latest['mae']:.2f}"),
            _bul(f"Tier 정확도 (high): {latest['tier_precision_high']:.0%}"),
        ]

    return blocks


async def _publish_to_notion(report: dict, notion_token: str, notion_db_id: str) -> None:
    """Notion 데이터베이스에 주간 ROI 리포트 페이지 생성."""
    try:
        import httpx
    except ImportError:
        print("httpx 미설치 - Notion 발행 건너뜀")
        return

    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    payload = {
        "parent": {"database_id": notion_db_id},
        "properties": {
            "Name": {"title": [{"text": {"content": f"ROI 리포트 {date_str}"}}]},
        },
        "children": _notion_blocks(report),
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.notion.com/v1/pages",
            json=payload,
            headers={
                "Authorization": f"Bearer {notion_token}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json",
            },
            timeout=30,
        )

    if resp.status_code == 200:
        page_id = resp.json().get("id", "")
        print(f"Notion 발행 완료: {page_id}")
    else:
        print(f"Notion 발행 실패: {resp.status_code} {resp.text[:200]}")


# ── 엔트리포인트 ──────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    args = _parse_args(argv)

    report = run(
        gdt_db=args.gdt_db,
        llm_db=args.llm_db,
        lookback_days=args.lookback_days,
    )

    _print_summary(report)

    # JSON 저장
    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    out_path = Path(args.json_out) if args.json_out else _OUT_DIR / f"roi_{date_str}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"json_out: {out_path.resolve()}")

    # Notion 발행 (선택)
    if not args.no_notion:
        notion_token = os.environ.get("NOTION_TOKEN", "")
        notion_db_id = os.environ.get("NOTION_ROI_DATABASE_ID", "")
        if notion_token and notion_db_id:
            import asyncio
            asyncio.run(_publish_to_notion(report, notion_token, notion_db_id))
        else:
            print("NOTION_TOKEN / NOTION_ROI_DATABASE_ID 미설정 - Notion 발행 건너뜀")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
