"""
getdaytrends v2.4 - Web Dashboard
FastAPI 기반 간단 대시보드: 히스토리 통계 + 최근 트렌드/트윗 조회 + LLM 비용 현황.

실행: uvicorn dashboard:app --reload --port 8010
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
except ImportError:
    raise ImportError(
        "dashboard 실행을 위해 fastapi와 uvicorn이 필요합니다:\n"
        "  pip install fastapi uvicorn[standard]"
    )

from config import AppConfig, VERSION
from db import get_connection, get_trend_stats, init_db

app = FastAPI(title="getdaytrends Dashboard", version=VERSION)

_config = AppConfig.from_env()

# Phase 3: 파이프라인 상태 추적 (인메모리)
_pipeline_status: dict = {
    "state": "idle",        # idle | running | error
    "last_run_at": None,
    "last_run_elapsed": None,
    "last_error": None,
    "trends_last_run": 0,
    "tweets_last_run": 0,
}


async def _get_conn():
    conn = await get_connection(_config.db_path, database_url=_config.database_url)
    await init_db(conn)
    return conn


# ── HTML 대시보드 ────────────────────────────────────────

_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>getdaytrends Dashboard v{version}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh}}
  header{{background:#1e293b;padding:16px 24px;display:flex;align-items:center;gap:12px;border-bottom:1px solid #334155}}
  header h1{{font-size:1.25rem;color:#f8fafc}}
  header .badge{{background:#6366f1;color:#fff;border-radius:4px;padding:2px 8px;font-size:.75rem}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px;padding:24px}}
  .card{{background:#1e293b;border-radius:8px;padding:20px;border:1px solid #334155}}
  .card .label{{font-size:.75rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em}}
  .card .value{{font-size:2rem;font-weight:700;color:#f1f5f9;margin-top:4px}}
  .card .sub{{font-size:.8rem;color:#64748b;margin-top:4px}}
  section{{padding:0 24px 24px}}
  section h2{{font-size:1rem;color:#94a3b8;margin-bottom:12px;padding-top:8px}}
  table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden}}
  th{{background:#334155;text-align:left;padding:10px 14px;font-size:.75rem;color:#94a3b8;text-transform:uppercase}}
  td{{padding:10px 14px;border-bottom:1px solid #1e293b;font-size:.85rem}}
  tr:hover td{{background:#273449}}
  .score-bar{{display:inline-block;height:8px;border-radius:4px;background:#6366f1;margin-right:6px;vertical-align:middle}}
  .score-low{{background:#ef4444}}
  .score-mid{{background:#f59e0b}}
  .score-high{{background:#22c55e}}
  .tag{{display:inline-block;padding:2px 6px;border-radius:3px;font-size:.7rem;background:#334155;color:#94a3b8;margin-right:4px}}
  .cost-row{{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #334155;font-size:.85rem}}
  .cost-row .day{{color:#94a3b8}}
  .cost-row .amt{{color:#f1f5f9;font-weight:600}}
  .pipeline-idle{{color:#22c55e}}.pipeline-running{{color:#f59e0b}}.pipeline-error{{color:#ef4444}}
  .budget-bar{{background:#334155;border-radius:4px;height:6px;margin-top:6px}}
  .budget-fill{{background:#6366f1;height:6px;border-radius:4px;transition:width .3s}}
  .budget-warn{{background:#ef4444}}
</style>
</head>
<body>
<header>
  <h1>📊 getdaytrends Dashboard</h1>
  <span class="badge">v{version}</span>
  <span id="pipeline-badge" style="margin-left:auto;padding:4px 10px;border-radius:4px;font-size:.8rem;background:#1e293b">⏳ 로딩중</span>
</header>

<div class="grid" id="stats-grid">
  <div class="card"><div class="label">총 실행</div><div class="value" id="s-runs">-</div></div>
  <div class="card"><div class="label">총 트렌드</div><div class="value" id="s-trends">-</div></div>
  <div class="card"><div class="label">평균 바이럴 점수</div><div class="value" id="s-score">-</div><div class="sub">/ 100</div></div>
  <div class="card"><div class="label">총 생성 트윗</div><div class="value" id="s-tweets">-</div></div>
  <div class="card"><div class="label">7일 LLM 비용</div><div class="value" id="s-cost">-</div><div class="sub" id="s-cost-sub"></div></div>
  <div class="card">
    <div class="label">오늘 예산</div>
    <div class="value" id="s-budget-cost">-</div>
    <div class="sub" id="s-budget-sub">/ $- 예산</div>
    <div class="budget-bar"><div class="budget-fill" id="s-budget-bar" style="width:0%"></div></div>
  </div>
</div>

<section>
  <h2>최근 트렌드 (상위 50개, 7일)</h2>
  <table>
    <thead><tr><th>#</th><th>키워드</th><th>바이럴</th><th>국가</th><th>가속도</th><th>날짜</th></tr></thead>
    <tbody id="trends-body"></tbody>
  </table>
</section>

<section>
  <h2>LLM 비용 (최근 7일)</h2>
  <div id="cost-list" style="background:#1e293b;border-radius:8px;padding:16px;max-width:400px"></div>
</section>

<script>
async function loadPipelineStatus() {{
  try {{
    const ps = await fetch('/api/pipeline_status').then(r=>r.json());
    const badge = document.getElementById('pipeline-badge');
    const stateMap = {{ idle:'✅ 대기중', running:'⚡ 실행중', error:'❌ 에러' }};
    const clsMap = {{ idle:'pipeline-idle', running:'pipeline-running', error:'pipeline-error' }};
    badge.textContent = stateMap[ps.state] || ps.state;
    badge.className = clsMap[ps.state] || '';
    badge.style.background = '#1e293b';
    if (ps.last_run_at) badge.title = '마지막 실행: ' + ps.last_run_at.slice(0,16) + (ps.last_run_elapsed ? ` (${ps.last_run_elapsed}초)` : '');

    // 예산 바
    const b = ps.budget || {{}};
    if (b.daily_budget_usd > 0) {{
      document.getElementById('s-budget-cost').textContent = '$' + (b.today_cost_usd||0).toFixed(4);
      document.getElementById('s-budget-sub').textContent = '/ $' + b.daily_budget_usd.toFixed(2) + ' 예산';
      const pct = Math.min(b.budget_used_pct||0, 100);
      const bar = document.getElementById('s-budget-bar');
      bar.style.width = pct + '%';
      if (pct >= 90) bar.classList.add('budget-warn');
    }}
  }} catch(e) {{ /* silent */ }}
}}

async function load() {{
  const [stats] = await Promise.all([
    fetch('/api/stats').then(r=>r.json()),
    loadPipelineStatus(),
  ]);
  document.getElementById('s-runs').textContent = stats.total_runs.toLocaleString();
  document.getElementById('s-trends').textContent = stats.total_trends.toLocaleString();
  document.getElementById('s-score').textContent = stats.avg_viral_score;
  document.getElementById('s-tweets').textContent = stats.total_tweets.toLocaleString();

  // LLM cost
  const cost7 = stats.llm_cost_7d ?? 0;
  document.getElementById('s-cost').textContent = '$' + cost7.toFixed(4);
  document.getElementById('s-cost-sub').textContent = '월 추정 $' + (cost7 / 7 * 30).toFixed(2);

  // Trends table
  const trends = await fetch('/api/trends?days=7&limit=50').then(r=>r.json());
  const tbody = document.getElementById('trends-body');
  trends.forEach((t, i) => {{
    const score = t.viral_potential;
    const cls = score >= 80 ? 'score-high' : score >= 65 ? 'score-mid' : 'score-low';
    const bar = `<span class="score-bar ${{cls}}" style="width:${{score * 0.8}}px"></span>${{score}}`;
    tbody.innerHTML += `<tr>
      <td>${{i+1}}</td>
      <td>${{t.keyword}}</td>
      <td>${{bar}}</td>
      <td><span class="tag">${{t.country}}</span></td>
      <td>${{t.trend_acceleration || '-'}}</td>
      <td>${{t.scored_at?.slice(0,16) || '-'}}</td>
    </tr>`;
  }});

  // Cost list
  const costList = document.getElementById('cost-list');
  if (stats.llm_daily) {{
    stats.llm_daily.forEach(row => {{
      costList.innerHTML += `<div class="cost-row">
        <span class="day">${{row.date}} <span class="tag">${{row.backend}}</span></span>
        <span class="amt">${{row.cost_usd.toFixed(4)}} <span style="color:#64748b">(${{row.calls}}콜)</span></span>
      </div>`;
    }});
  }} else {{
    costList.textContent = 'LLM 비용 데이터 없음';
  }}
}}
load();
// 30초마다 파이프라인 상태 갱신
setInterval(loadPipelineStatus, 30000);
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def index():
    return _HTML.format(version=VERSION)


# ── API Endpoints ────────────────────────────────────────

@app.get("/api/stats")
async def api_stats():
    conn = await _get_conn()
    stats = await get_trend_stats(conn)

    # LLM 비용 통합
    llm_cost_7d = 0.0
    llm_daily = []
    try:
        from shared.llm.stats import CostTracker, _DB_PATH as llm_db_path
        if llm_db_path.exists():
            tracker = CostTracker(persist=True)
            daily = tracker.get_daily_stats(7)
            tracker.close()
            llm_daily = daily
            llm_cost_7d = sum(r["cost_usd"] for r in daily)
    except Exception:
        pass

    await conn.close()
    return JSONResponse({
        **stats,
        "llm_cost_7d": round(llm_cost_7d, 6),
        "llm_daily": llm_daily,
    })


@app.get("/api/trends")
async def api_trends(days: int = Query(7, ge=1, le=90), limit: int = Query(50, ge=1, le=200)):
    from datetime import timedelta
    conn = await _get_conn()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    cursor = await conn.execute(
        """SELECT keyword, viral_potential, trend_acceleration, top_insight,
                  country, scored_at
           FROM trends WHERE scored_at >= ?
           ORDER BY viral_potential DESC LIMIT ?""",
        (cutoff, limit)
    )
    rows = await cursor.fetchall()
    await conn.close()
    return JSONResponse([dict(r) for r in rows])


@app.get("/api/tweets")
async def api_tweets(
    trend_keyword: str = Query(None),
    days: int = Query(3, ge=1, le=30),
    limit: int = Query(30, ge=1, le=100),
):
    from datetime import timedelta
    conn = await _get_conn()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    if trend_keyword:
        cursor = await conn.execute(
            """SELECT tw.tweet_type, tw.content, tw.content_type, tw.char_count,
                      tw.status, tw.generated_at, tr.keyword
               FROM tweets tw JOIN trends tr ON tw.trend_id = tr.id
               WHERE tr.keyword LIKE ? AND tw.generated_at >= ?
               ORDER BY tw.generated_at DESC LIMIT ?""",
            (f"%{trend_keyword}%", cutoff, limit)
        )
    else:
        # NOTE: Using a query logic equivalent to original
        # This branch wasn't explicitly using trend DB filter for keyword, but date.
        cursor = await conn.execute(
            """SELECT tw.tweet_type, tw.content, tw.content_type, tw.char_count,
                      tw.status, tw.generated_at, tr.keyword
               FROM tweets tw JOIN trends tr ON tw.trend_id = tr.id
               WHERE tw.generated_at >= ?
               ORDER BY tw.generated_at DESC LIMIT ?""",
            (cutoff, limit)
        )
    
    rows = await cursor.fetchall()
    await conn.close()
    return JSONResponse([dict(r) for r in rows])


@app.get("/api/runs")
async def api_runs(limit: int = Query(20, ge=1, le=100)):
    conn = await _get_conn()
    cursor = await conn.execute(
        """SELECT run_uuid, started_at, finished_at, country,
                  trends_collected, tweets_generated, tweets_saved, errors
           FROM runs ORDER BY started_at DESC LIMIT ?""",
        (limit,)
    )
    rows = await cursor.fetchall()
    await conn.close()
    return JSONResponse([dict(r) for r in rows])


@app.get("/api/pipeline_status")
def api_pipeline_status():
    """Phase 3: 실시간 파이프라인 상태 + 예산 현황."""
    status = dict(_pipeline_status)

    # 일별 예산 현황 추가
    budget_info = {"daily_budget_usd": _config.daily_budget_usd, "today_cost_usd": 0.0, "budget_used_pct": 0.0}
    try:
        from datetime import date
        from shared.llm.stats import CostTracker
        from shared.llm.stats import _DB_PATH as llm_db_path
        if llm_db_path.exists():
            tracker = CostTracker(persist=True)
            daily = tracker.get_daily_stats(1)
            tracker.close()
            today = str(date.today())
            today_cost = sum(r["cost_usd"] for r in daily if r.get("date") == today)
            budget_info["today_cost_usd"] = round(today_cost, 6)
            if _config.daily_budget_usd > 0:
                budget_info["budget_used_pct"] = round(today_cost / _config.daily_budget_usd * 100, 1)
    except Exception:
        pass

    status["budget"] = budget_info
    return JSONResponse(status)


@app.post("/api/pipeline_status")
def update_pipeline_status(state: str, error: str = "", trends: int = 0, tweets: int = 0, elapsed: float = 0.0):
    """main.py에서 파이프라인 상태 업데이트 (내부용)."""
    _pipeline_status["state"] = state
    _pipeline_status["last_run_at"] = datetime.now().isoformat()
    if error:
        _pipeline_status["last_error"] = error
    if trends:
        _pipeline_status["trends_last_run"] = trends
    if tweets:
        _pipeline_status["tweets_last_run"] = tweets
    if elapsed:
        _pipeline_status["last_run_elapsed"] = round(elapsed, 1)
    return {"ok": True}
