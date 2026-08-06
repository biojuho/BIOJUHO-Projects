"""
getdaytrends — Dashboard HTML Template.

Extracted from dashboard.py for maintainability.
Contains the full Pro Dashboard UI: Chart.js panels, KPI cards,
TAP Board, Deal Room, and auto-refresh logic.
"""


def get_dashboard_html(version: str) -> str:
    """Return the full dashboard HTML with version string interpolated."""
    return _HTML.format(version=version)


_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>getdaytrends Pro Dashboard v{version}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Inter',sans-serif;background:#0a0e1a;color:#e2e8f0;min-height:100vh}}

  /* ── Header ── */
  header{{
    background:linear-gradient(135deg,#0f172a 0%,#1a1f3a 100%);
    padding:16px 28px;display:flex;align-items:center;gap:14px;
    border-bottom:1px solid rgba(99,102,241,.25);
    box-shadow:0 4px 24px rgba(0,0,0,.3)
  }}
  header h1{{font-size:1.2rem;color:#f8fafc;font-weight:600}}
  .badge{{background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;border-radius:6px;padding:3px 10px;font-size:.7rem;font-weight:600}}
  .pulse{{animation:pulse 2s infinite}}
  @keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.5}}}}

  /* ── Status pill ── */
  .status-pill{{
    margin-left:auto;padding:6px 14px;border-radius:20px;font-size:.78rem;font-weight:600;
    transition:all .3s ease;cursor:default
  }}
  .st-idle{{background:rgba(34,197,94,.15);color:#22c55e;border:1px solid rgba(34,197,94,.3)}}
  .st-running{{background:rgba(245,158,11,.15);color:#f59e0b;border:1px solid rgba(245,158,11,.3)}}
  .st-error{{background:rgba(239,68,68,.15);color:#ef4444;border:1px solid rgba(239,68,68,.3)}}
  .dashboard-warning-banner{{
    display:none;align-items:flex-start;gap:12px;margin:12px 28px 0;padding:14px 16px;
    border-radius:12px;border:1px solid rgba(245,158,11,.32);
    background:linear-gradient(135deg,rgba(120,53,15,.45),rgba(69,26,3,.62));
    color:#fde68a
  }}
  .dashboard-warning-banner.show{{display:flex}}
  .dashboard-warning-banner strong{{font-size:.8rem;white-space:nowrap}}
  .dashboard-warning-copy{{display:flex;flex-wrap:wrap;gap:8px;align-items:center;font-size:.78rem;line-height:1.5}}
  .dashboard-warning-chip{{
    display:inline-flex;align-items:center;padding:3px 8px;border-radius:999px;
    background:rgba(251,191,36,.16);border:1px solid rgba(251,191,36,.18);color:#fcd34d;font-size:.72rem;font-weight:700
  }}

  /* ── KPI Grid ── */
  .kpi-grid{{display:grid;grid-template-columns:repeat(6,1fr);gap:14px;padding:20px 28px}}
  @media(max-width:1200px){{.kpi-grid{{grid-template-columns:repeat(3,1fr)}}}}
  @media(max-width:768px){{.kpi-grid{{grid-template-columns:repeat(2,1fr)}}}}
  .kpi{{
    background:linear-gradient(145deg,#131729,#181d35);
    border-radius:12px;padding:18px 20px;
    border:1px solid rgba(99,102,241,.12);
    transition:transform .2s,border-color .3s
  }}
  .kpi:hover{{transform:translateY(-2px);border-color:rgba(99,102,241,.4)}}
  .kpi .label{{font-size:.68rem;color:#64748b;text-transform:uppercase;letter-spacing:.06em;font-weight:500}}
  .kpi .value{{font-size:1.8rem;font-weight:700;color:#f1f5f9;margin-top:4px;line-height:1}}
  .kpi .sub{{font-size:.72rem;color:#475569;margin-top:6px}}
  .kpi .trend-up{{color:#22c55e}}
  .kpi .trend-down{{color:#ef4444}}

  /* ── Budget bar ── */
  .budget-track{{background:#1e293b;border-radius:4px;height:6px;margin-top:8px;overflow:hidden}}
  .budget-fill{{height:6px;border-radius:4px;transition:width .8s cubic-bezier(.4,0,.2,1)}}
  .bf-ok{{background:linear-gradient(90deg,#6366f1,#8b5cf6)}}
  .bf-warn{{background:linear-gradient(90deg,#f59e0b,#ef4444)}}

  /* ── Charts layout ── */
  .charts-row{{display:grid;grid-template-columns:2fr 1fr;gap:14px;padding:0 28px 14px}}
  .charts-row-2{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;padding:0 28px 14px}}
  @media(max-width:1200px){{.charts-row,.charts-row-2{{grid-template-columns:1fr}}}}
  .panel{{
    background:linear-gradient(145deg,#131729,#181d35);
    border-radius:12px;padding:20px;
    border:1px solid rgba(99,102,241,.12)
  }}
  .panel h3{{font-size:.82rem;color:#94a3b8;margin-bottom:14px;font-weight:600;text-transform:uppercase;letter-spacing:.04em}}
  canvas{{max-height:280px}}

  /* ── Table ── */
  .tbl-wrap{{padding:0 28px 28px}}
  table{{width:100%;border-collapse:collapse;background:#131729;border-radius:12px;overflow:hidden;border:1px solid rgba(99,102,241,.1)}}
  th{{background:#181d35;text-align:left;padding:11px 16px;font-size:.7rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em;font-weight:600}}
  td{{padding:11px 16px;border-bottom:1px solid rgba(99,102,241,.06);font-size:.82rem}}
  tr{{transition:background .15s}}
  tr:hover td{{background:rgba(99,102,241,.06)}}

  /* ── Score chip ── */
  .tap-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}}
  @media(max-width:1200px){{.tap-grid{{grid-template-columns:1fr}}}}
  .tap-card{{background:linear-gradient(145deg,#0f172a,#131a2b);border:1px solid rgba(99,102,241,.12);border-radius:12px;padding:16px;min-height:180px}}
  .tap-deal-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}}
  @media(max-width:1200px){{.tap-deal-grid{{grid-template-columns:1fr}}}}
  .tap-deal-card{{background:linear-gradient(145deg,#0f172a,#151e34);border:1px solid rgba(245,158,11,.18);border-radius:12px;padding:16px}}
  .tap-deal-top{{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:10px}}
  .tap-price{{font-size:1.1rem;font-weight:800;color:#fbbf24}}
  .tap-cta{{display:inline-flex;align-items:center;justify-content:center;border-radius:999px;padding:7px 12px;background:rgba(245,158,11,.16);color:#fcd34d;font-size:.75rem;font-weight:700;margin-top:10px}}
  .tap-outline{{display:grid;gap:6px;margin-top:12px}}
  .tap-outline-item{{font-size:.76rem;color:#cbd5e1;line-height:1.45}}
  .tap-head{{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:12px}}
  .tap-title{{font-size:1rem;font-weight:700;color:#f8fafc;line-height:1.3}}
  .tap-badge{{padding:4px 8px;border-radius:999px;font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em}}
  .tap-free{{background:rgba(34,197,94,.14);color:#22c55e}}
  .tap-premium{{background:rgba(245,158,11,.14);color:#f59e0b}}
  .tap-meta{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}}
  .tap-chip{{padding:3px 8px;border-radius:999px;background:rgba(99,102,241,.12);color:#a5b4fc;font-size:.72rem}}
  .tap-copy{{color:#cbd5e1;font-size:.84rem;line-height:1.5;margin-bottom:10px}}
  .tap-notes{{color:#94a3b8;font-size:.76rem;line-height:1.45}}
  .tap-lock{{color:#64748b;font-size:.72rem;margin-top:10px}}
  .tap-actions{{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0 14px}}
  .tap-btn{{
    appearance:none;border:none;border-radius:10px;padding:10px 14px;cursor:pointer;
    background:linear-gradient(135deg,#f59e0b,#f97316);color:#0f172a;font-size:.78rem;
    font-weight:700;letter-spacing:.01em;transition:transform .15s ease,opacity .15s ease
  }}
  .tap-btn:hover{{transform:translateY(-1px)}}
  .tap-btn:disabled{{opacity:.55;cursor:wait;transform:none}}
  .tap-btn-ghost{{background:rgba(99,102,241,.14);color:#c7d2fe;border:1px solid rgba(99,102,241,.18)}}
  .tap-summary{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:8px}}
  .tap-summary-card{{background:#0f172a;border:1px solid rgba(99,102,241,.1);border-radius:10px;padding:12px}}
  .tap-summary-label{{font-size:.68rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px}}
  .tap-summary-value{{font-size:1.15rem;color:#f8fafc;font-weight:700}}
  .tap-control-row{{display:grid;grid-template-columns:1.4fr 1fr 1fr;gap:10px;margin:12px 0 8px}}
  .tap-control{{display:flex;flex-direction:column;gap:6px}}
  .tap-control span{{font-size:.68rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em}}
  .tap-input{{
    width:100%;border-radius:10px;border:1px solid rgba(99,102,241,.18);
    background:#0f172a;color:#e2e8f0;padding:10px 12px;font-size:.78rem;outline:none
  }}
  .tap-input:focus{{border-color:rgba(99,102,241,.4);box-shadow:0 0 0 2px rgba(99,102,241,.12)}}
  .tap-preset-strip{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;align-items:center}}
  .tap-preset-btn{{
    appearance:none;border:1px solid rgba(99,102,241,.14);border-radius:999px;
    background:#0f172a;color:#cbd5e1;padding:6px 10px;font-size:.72rem;cursor:pointer;
    transition:transform .15s ease,border-color .15s ease,background .15s ease
  }}
  .tap-preset-btn:hover{{transform:translateY(-1px);border-color:rgba(99,102,241,.35)}}
  .tap-preset-btn-active{{background:rgba(99,102,241,.16);color:#eef2ff;border-color:rgba(99,102,241,.38)}}
  .tap-preset-empty{{font-size:.72rem;color:#64748b}}
  .tap-alert-list{{display:grid;gap:10px}}
  .tap-alert-item{{background:#0f172a;border:1px solid rgba(99,102,241,.1);border-radius:10px;padding:12px}}
  .tap-alert-top{{display:flex;justify-content:space-between;gap:10px;align-items:flex-start;margin-bottom:8px}}
  .tap-alert-title{{font-size:.88rem;font-weight:700;color:#f8fafc}}
  .tap-alert-body{{font-size:.78rem;color:#cbd5e1;line-height:1.45}}
  .tap-alert-meta{{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}}
  .tap-outcome-title{{margin-top:14px;margin-bottom:10px;font-size:.72rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em}}
  .tap-outcome-list{{display:grid;gap:10px}}
  .tap-outcome-card{{background:#0f172a;border:1px solid rgba(99,102,241,.1);border-radius:10px;padding:12px}}
  .tap-outcome-card-failed{{border-color:rgba(239,68,68,.24)}}
  .tap-outcome-card-success{{border-color:rgba(34,197,94,.24)}}
  .tap-outcome-time{{font-size:.72rem;color:#64748b}}
  .tap-outcome-details{{margin-top:10px;border-top:1px solid rgba(99,102,241,.08);padding-top:10px}}
  .tap-outcome-details summary{{cursor:pointer;color:#a5b4fc;font-size:.74rem}}
  .tap-outcome-detail-list{{display:grid;gap:8px;margin-top:10px}}
  .tap-outcome-detail-item{{font-size:.74rem;color:#cbd5e1;line-height:1.45}}
  .tap-outcome-error{{color:#fca5a5}}
  .tap-status{{min-height:22px;font-size:.76rem;color:#94a3b8}}
  @media(max-width:1200px){{.tap-summary{{grid-template-columns:1fr 1fr}}.tap-control-row{{grid-template-columns:1fr}}}}
  .chip{{display:inline-flex;align-items:center;gap:4px;padding:3px 10px;border-radius:20px;font-size:.72rem;font-weight:600}}
  .chip-high{{background:rgba(34,197,94,.15);color:#22c55e}}
  .chip-mid{{background:rgba(245,158,11,.15);color:#f59e0b}}
  .chip-low{{background:rgba(239,68,68,.15);color:#ef4444}}
  .tag{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.68rem;background:rgba(99,102,241,.15);color:#818cf8}}

  /* ── X opportunity radar ── */
  .x-radar-panel{{margin:16px 28px 14px;border-color:rgba(239,68,68,.28);background:linear-gradient(145deg,#151525,#1b1523)}}
  .x-radar-intro{{color:#cbd5e1;font-size:.82rem;line-height:1.55;margin:-4px 0 14px}}
  .x-radar-controls{{display:grid;grid-template-columns:2fr .6fr auto;gap:10px;margin-bottom:10px}}
  .x-radar-status{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;min-height:28px;margin-bottom:12px;color:#94a3b8;font-size:.76rem}}
  .x-radar-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}}
  .x-radar-card{{background:#0f172a;border:1px solid rgba(239,68,68,.16);border-radius:12px;padding:16px}}
  .x-radar-card-top{{display:flex;justify-content:space-between;gap:14px;align-items:flex-start}}
  .x-radar-keyword{{font-size:1.05rem;font-weight:800;color:#f8fafc;line-height:1.35}}
  .x-radar-score{{min-width:58px;text-align:center;border-radius:12px;padding:8px 10px;background:rgba(239,68,68,.13);color:#fca5a5;font-size:1.05rem;font-weight:800}}
  .x-radar-score small{{display:block;font-size:.58rem;color:#94a3b8;font-weight:600;margin-top:2px}}
  .x-radar-reasons{{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}}
  .x-radar-reason{{padding:3px 7px;border-radius:999px;background:rgba(245,158,11,.11);color:#fbbf24;font-size:.69rem}}
  .x-radar-sources{{display:grid;gap:8px;margin-top:12px}}
  .x-radar-source{{display:block;text-decoration:none;background:rgba(15,23,42,.85);border:1px solid rgba(148,163,184,.12);border-radius:9px;padding:10px 11px;transition:border-color .15s,transform .15s}}
  .x-radar-source:hover{{border-color:rgba(99,102,241,.42);transform:translateY(-1px)}}
  .x-radar-source-name{{font-size:.68rem;color:#818cf8;margin-bottom:4px}}
  .x-radar-source-title{{font-size:.79rem;color:#e2e8f0;line-height:1.45}}
  .x-radar-actions{{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}}
  .x-radar-link{{display:inline-flex;align-items:center;text-decoration:none;border-radius:9px;padding:8px 11px;background:rgba(99,102,241,.13);border:1px solid rgba(99,102,241,.18);color:#c7d2fe;font-size:.73rem;font-weight:700}}
  .x-radar-empty{{color:#94a3b8;font-size:.8rem;padding:14px}}
  @media(max-width:1000px){{.x-radar-controls,.x-radar-grid{{grid-template-columns:1fr}}}}

  /* ── Direct community early detector ── */
  .fast-viral-panel{{margin:16px 28px 14px;border-color:rgba(34,197,94,.28);background:linear-gradient(145deg,#101c1b,#132025)}}
  .fast-viral-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}}
  .fast-viral-card{{background:#0f172a;border:1px solid rgba(34,197,94,.16);border-radius:12px;padding:15px}}
  .fast-viral-score{{min-width:58px;text-align:center;border-radius:12px;padding:8px 10px;background:rgba(34,197,94,.13);color:#86efac;font-size:1.05rem;font-weight:800}}
  .fast-viral-score small{{display:block;font-size:.58rem;color:#94a3b8;font-weight:600;margin-top:2px}}
  .fast-viral-early{{color:#86efac;font-weight:700}}
  @media(max-width:1200px){{.fast-viral-grid{{grid-template-columns:1fr 1fr}}}}
  @media(max-width:800px){{.fast-viral-grid{{grid-template-columns:1fr}}}}

  /* ── Reference library ── */
  .reference-panel{{margin:16px 28px 14px}}
  .reference-live-bar{{display:grid;grid-template-columns:2fr .7fr auto;gap:10px;margin-bottom:10px}}
  .reference-live-status{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;min-height:28px;margin-bottom:12px;color:#94a3b8;font-size:.76rem}}
  .live-dot{{width:8px;height:8px;border-radius:999px;background:#ef4444;box-shadow:0 0 0 5px rgba(239,68,68,.12);animation:pulse 2s infinite}}
  .reference-connector-note{{color:#64748b;font-size:.7rem}}
  .reference-toolbar{{display:grid;grid-template-columns:2fr 1fr 1fr auto;gap:10px;margin-bottom:12px}}
  .reference-form{{display:grid;grid-template-columns:1.4fr 2fr 1fr 1fr .7fr;gap:10px;margin-bottom:12px}}
  .reference-summary{{grid-column:1 / -2;min-height:68px;resize:vertical}}
  .reference-stats{{display:flex;gap:8px;flex-wrap:wrap;margin:4px 0 14px}}
  .reference-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}}
  .reference-card{{background:#0f172a;border:1px solid rgba(99,102,241,.12);border-radius:12px;padding:15px}}
  .reference-card-top{{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}}
  .reference-title{{font-size:.95rem;color:#f8fafc;font-weight:700;line-height:1.4}}
  .reference-title a{{color:inherit;text-decoration:none}}
  .reference-title a:hover{{color:#a5b4fc}}
  .reference-copy{{margin-top:10px;color:#cbd5e1;font-size:.78rem;line-height:1.55;white-space:pre-wrap}}
  .reference-details{{margin-top:10px;color:#94a3b8;font-size:.76rem}}
  .reference-details summary{{cursor:pointer;color:#a5b4fc}}
  .reference-actions{{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}}
  .reference-memo{{width:100%;min-height:64px;margin-top:10px;resize:vertical}}
  @media(max-width:1000px){{
    .reference-live-bar,.reference-toolbar,.reference-form{{grid-template-columns:1fr}}
    .reference-summary{{grid-column:auto}}
    .reference-grid{{grid-template-columns:1fr}}
  }}

  /* ── Skeleton loading ── */
  .skeleton{{background:linear-gradient(90deg,#1e293b 25%,#334155 50%,#1e293b 75%);background-size:200% 100%;animation:shimmer 1.5s infinite}}
  @keyframes shimmer{{0%{{background-position:200% 0}}100%{{background-position:-200% 0}}}}
  .sk-block{{height:28px;border-radius:6px;margin-bottom:8px}}

  /* ── Footer ── */
  .footer{{text-align:center;padding:16px;color:#334155;font-size:.7rem}}
  .footer span{{color:#6366f1}}

  /* ── Toast ── */
  .toast{{
    position:fixed;bottom:24px;right:24px;padding:12px 20px;border-radius:8px;
    background:rgba(34,197,94,.9);color:#fff;font-size:.82rem;font-weight:500;
    transform:translateY(100px);opacity:0;transition:all .4s cubic-bezier(.4,0,.2,1);z-index:999
  }}
  .toast.show{{transform:translateY(0);opacity:1}}
</style>
</head>
<body>

<header>
  <h1>📊 getdaytrends Pro</h1>
  <span class="badge">v{version}</span>
  <div id="status-pill" class="status-pill st-idle">⏳ 로딩중</div>
</header>
<div id="dashboard-warning-banner" class="dashboard-warning-banner" role="status" aria-live="polite"></div>

<!-- Direct Community Early Detector -->
<section class="panel fast-viral-panel" aria-labelledby="fast-viral-title">
  <h3 id="fast-viral-title">🚨 커뮤니티 바이럴 조기감지</h3>
  <p class="x-radar-intro">개드립·더쿠 HOT·루리웹 베스트·FMKorea를 직접 확인하고, 연결 제한이나 후보 부족 때는 IssueLink의 다른 커뮤니티 원문으로 보완합니다. 댓글·조회·추천·교차확산으로 X 노출 적합도를 계산하며 선행시간은 두 최초 감지 시각이 모두 있을 때만 표시합니다.</p>
  <div class="x-radar-controls">
    <div class="reference-connector-note">스포츠·정치·증시·종목·기업 실적·부동산과 성인성 제목은 제외합니다. AAGAG는 robots 정책에 따라 자동 수집하지 않습니다.</div>
    <select id="fast-viral-limit" class="tap-input" aria-label="조기 후보 표시 개수">
      <option value="6">상위 6개</option>
      <option value="12" selected>상위 12개</option>
      <option value="20">상위 20개</option>
    </select>
    <button id="fast-viral-refresh" type="button" class="tap-btn" onclick="refreshFastViral(false)">지금 직접 확인</button>
  </div>
  <div id="fast-viral-status" class="x-radar-status" aria-live="polite">
    <span class="live-dot"></span><span>다중 커뮤니티 원문·최초 감지 시각 확인 준비 중</span>
  </div>
  <div id="fast-viral-list" class="fast-viral-grid">
    <div class="skeleton sk-block" style="height:190px"></div>
    <div class="skeleton sk-block" style="height:190px"></div>
    <div class="skeleton sk-block" style="height:190px"></div>
  </div>
</section>

<!-- X Breaking / Viral Source Radar -->
<section class="panel x-radar-panel" aria-labelledby="x-radar-title">
  <h3 id="x-radar-title">⚡ X 속보·바이럴 원문 레이더</h3>
  <p class="x-radar-intro">독립 원문·Threads 교차 근거가 있는 주제와, 공개 X 상위 5위 반복 또는 연속 순위 상승이 확인된 X 네이티브 단어를 분리해 표시합니다. 공개 X는 90초 캐시·2분 자동 갱신이며 수동 확인은 캐시를 우회합니다. 스포츠·정치·증시·종목·기업 실적·부동산은 표시하지 않으며 자동 문안 생성이나 게시 기능은 없습니다.</p>
  <div class="x-radar-controls">
    <input id="x-radar-focus" class="tap-input" maxlength="500" placeholder="관심 분야 선택 입력 — 예: AI, 사건, 크리에이터 (비워두면 전체)">
    <select id="x-radar-limit" class="tap-input" aria-label="표시 개수">
      <option value="10">상위 10개</option>
      <option value="20" selected>상위 20개</option>
      <option value="30">상위 30개</option>
    </select>
    <button id="x-radar-refresh" type="button" class="tap-btn" onclick="refreshXRadar(false)">지금 새로 확인</button>
  </div>
  <div id="x-radar-status" class="x-radar-status" aria-live="polite">
    <span class="live-dot"></span><span>Google 실시간 검색과 공개 X 트렌드 연결 준비 중</span>
  </div>
  <div id="x-radar-list" class="x-radar-grid">
    <div class="skeleton sk-block" style="height:220px"></div>
    <div class="skeleton sk-block" style="height:220px"></div>
  </div>
</section>

<!-- Live Creator Reference Radar -->
<section class="panel reference-panel" aria-labelledby="reference-library-title">
  <h3 id="reference-library-title">🔴 LIVE 크리에이터 레퍼런스 레이더</h3>
  <div class="reference-live-bar">
    <input id="reference-live-keywords" class="tap-input" value="AI 콘텐츠, 유튜브 성장, 콘텐츠 마케팅" maxlength="500" aria-label="라이브 수집 키워드">
    <select id="reference-live-limit" class="tap-input" aria-label="키워드당 수집 개수">
      <option value="3">키워드당 3개</option>
      <option value="5" selected>키워드당 5개</option>
      <option value="8">키워드당 8개</option>
    </select>
    <button id="reference-live-refresh" type="button" class="tap-btn" onclick="refreshLiveReferences(false)">지금 라이브 수집</button>
  </div>
  <div id="reference-live-status" class="reference-live-status" aria-live="polite">
    <span class="live-dot"></span><span>YouTube 공개 메타데이터 연결 준비 중</span>
    <span class="reference-connector-note">Instagram · TikTok · Threads · X는 공식 API 연결 전까지 비활성</span>
  </div>
  <div class="reference-toolbar">
    <input id="reference-query" class="tap-input" placeholder="키워드·제목·대본·메모 검색" oninput="loadReferenceLibrary()">
    <select id="reference-platform-filter" class="tap-input" onchange="loadReferenceLibrary()">
      <option value="">모든 플랫폼</option>
      <option value="youtube">YouTube</option>
      <option value="instagram">Instagram</option>
      <option value="tiktok">TikTok</option>
      <option value="threads">Threads</option>
      <option value="x">X</option>
      <option value="other">기타</option>
    </select>
    <select id="reference-state-filter" class="tap-input" onchange="loadReferenceLibrary()">
      <option value="">전체 상태</option>
      <option value="saved">즐겨찾기</option>
      <option value="unread">안 읽음</option>
      <option value="recommended">추천 80+</option>
    </select>
    <button type="button" class="tap-btn tap-btn-ghost" onclick="loadReferenceLibrary()">목록 새로고침</button>
  </div>
  <details class="reference-details">
    <summary>URL로 직접 레퍼런스 추가</summary>
    <form id="reference-form" class="reference-form" onsubmit="createReference(event)" style="margin-top:12px">
      <input id="reference-title" class="tap-input" required maxlength="240" placeholder="콘텐츠 제목">
      <input id="reference-url" class="tap-input" required type="url" maxlength="2048" placeholder="https:// 원본 URL">
      <input id="reference-keyword" class="tap-input" maxlength="160" placeholder="수집 키워드">
      <select id="reference-platform" class="tap-input" required>
        <option value="youtube">YouTube</option>
        <option value="instagram">Instagram</option>
        <option value="tiktok">TikTok</option>
        <option value="threads">Threads</option>
        <option value="x">X</option>
        <option value="other">기타</option>
      </select>
      <input id="reference-score" class="tap-input" type="number" min="0" max="100" value="80" aria-label="추천 점수">
      <textarea id="reference-summary" class="tap-input reference-summary" maxlength="20000" placeholder="핵심 요약이나 적용 아이디어"></textarea>
      <button type="submit" class="tap-btn">레퍼런스 추가</button>
    </form>
  </details>
  <div id="reference-stats" class="reference-stats" aria-live="polite"></div>
  <div id="reference-list" class="reference-grid">
    <div class="skeleton sk-block" style="height:170px"></div>
    <div class="skeleton sk-block" style="height:170px"></div>
  </div>
</section>

<!-- KPI Cards -->
<div class="kpi-grid" id="kpi-grid">
  <div class="kpi"><div class="label">총 실행</div><div class="value skeleton sk-block" id="k-runs"></div></div>
  <div class="kpi"><div class="label">총 트렌드</div><div class="value skeleton sk-block" id="k-trends"></div></div>
  <div class="kpi"><div class="label">평균 바이럴</div><div class="value skeleton sk-block" id="k-score"></div><div class="sub">/ 100</div></div>
  <div class="kpi"><div class="label">총 트윗</div><div class="value skeleton sk-block" id="k-tweets"></div></div>
  <div class="kpi"><div class="label">7일 LLM 비용</div><div class="value skeleton sk-block" id="k-cost"></div><div class="sub" id="k-cost-sub"></div></div>
  <div class="kpi">
    <div class="label">오늘 예산 사용</div>
    <div class="value skeleton sk-block" id="k-budget"></div>
    <div class="sub" id="k-budget-sub"></div>
    <div class="budget-track"><div class="budget-fill bf-ok" id="k-budget-bar" style="width:0%"></div></div>
  </div>
</div>

<!-- Charts Row 1: Trends timeline + Category pie -->
<div class="charts-row">
  <div class="panel">
    <h3>🔥 바이럴 스코어 타임라인 (7일)</h3>
    <canvas id="chart-timeline"></canvas>
  </div>
  <div class="panel">
    <h3>📂 카테고리 분포</h3>
    <canvas id="chart-category"></canvas>
  </div>
</div>

<!-- Charts Row 2: Source quality + Cost + Acceleration -->
<div class="charts-row-2">
  <div class="panel">
    <h3>📡 소스 품질</h3>
    <canvas id="chart-source"></canvas>
  </div>
  <div class="panel">
    <h3>💰 일별 LLM 비용</h3>
    <canvas id="chart-cost"></canvas>
  </div>
  <div class="panel">
    <h3>🚀 트렌드 가속도 TOP 10</h3>
    <canvas id="chart-accel"></canvas>
  </div>
</div>

<!-- Row 3: A/B Test + Logs -->
<div class="charts-row">
  <div class="panel">
    <h3>🧪 M/A A/B 테스트 성과 (DailyNews)</h3>
    <div style="display:flex;gap:20px;height:100%;align-items:center;" id="ab-test-content">
      <div class="skeleton sk-block" style="flex:1;height:80px"></div>
      <div class="skeleton sk-block" style="flex:1;height:80px"></div>
    </div>
  </div>
  <div class="panel">
    <h3>📋 실시간 파이프라인 로그 (Loki / 로컬)</h3>
    <div id="log-viewer" style="background:#0f172a;padding:12px;border-radius:6px;height:240px;overflow-y:auto;font-family:monospace;font-size:0.75rem;color:#a5b4fc;">
      <div class="skeleton sk-block"></div>
      <div class="skeleton sk-block" style="width:70%"></div>
      <div class="skeleton sk-block" style="width:40%"></div>
    </div>
  </div>
</div>

<!-- TAP Board -->
<div class="charts-row">
  <div class="panel">
    <h3>⚡ TAP Pro: Cross-country First-Mover Radar</h3>
    <div id="tap-board" class="tap-grid">
      <div class="skeleton sk-block" style="height:180px"></div>
      <div class="skeleton sk-block" style="height:180px"></div>
      <div class="skeleton sk-block" style="height:180px"></div>
    </div>
  </div>
  <div class="panel">
    <h3>??TAP Alert Queue Ops</h3>
    <div id="tap-alert-summary" class="tap-summary">
      <div class="tap-summary-card"><div class="tap-summary-label">Queued</div><div class="tap-summary-value skeleton sk-block" style="height:24px"></div></div>
      <div class="tap-summary-card"><div class="tap-summary-label">Dispatched</div><div class="tap-summary-value skeleton sk-block" style="height:24px"></div></div>
      <div class="tap-summary-card"><div class="tap-summary-label">Failed</div><div class="tap-summary-value skeleton sk-block" style="height:24px"></div></div>
      <div class="tap-summary-card"><div class="tap-summary-label">Channels</div><div class="tap-summary-value skeleton sk-block" style="height:24px"></div></div>
    </div>
    <div class="tap-control-row">
      <label class="tap-control">
        <span>Target market</span>
        <input id="tap-target-country" class="tap-input" placeholder="all markets" onchange="syncTapOpsView()">
      </label>
      <label class="tap-control">
        <span>Lifecycle</span>
        <select id="tap-alert-lifecycle" class="tap-input" onchange="loadTapAlerts()">
          <option value="queued">Queued</option>
          <option value="">All states</option>
          <option value="dispatched">Dispatched</option>
          <option value="failed">Failed</option>
        </select>
      </label>
      <label class="tap-control">
        <span>Batch size</span>
        <select id="tap-alert-limit" class="tap-input" onchange="loadTapAlerts()">
          <option value="5">5</option>
          <option value="6" selected>6</option>
          <option value="10">10</option>
          <option value="20">20</option>
        </select>
      </label>
    </div>
    <div class="tap-preset-strip">
      <div id="tap-preset-strip" class="tap-preset-strip">
        <span class="tap-preset-empty">Preset markets will appear here.</span>
      </div>
      <button id="tap-save-preset-btn" class="tap-btn tap-btn-ghost" onclick="saveCurrentTapPreset()">Save preset</button>
      <button id="tap-clear-presets-btn" class="tap-btn tap-btn-ghost" onclick="resetTapPresets()">Reset presets</button>
    </div>
    <div class="tap-actions">
      <button id="tap-dispatch-btn" class="tap-btn" onclick="dispatchTapAlerts(false)">Dispatch queued</button>
      <button id="tap-dry-run-btn" class="tap-btn tap-btn-ghost" onclick="dispatchTapAlerts(true)">Dry run</button>
      <button id="tap-refresh-btn" class="tap-btn tap-btn-ghost" onclick="syncTapOpsView()">Refresh queue</button>
    </div>
    <div id="tap-alert-status" class="tap-status">Queue status will appear here.</div>
    <div id="tap-alert-list" class="tap-alert-list">
      <div class="skeleton sk-block" style="height:86px"></div>
      <div class="skeleton sk-block" style="height:86px"></div>
      <div class="skeleton sk-block" style="height:86px"></div>
    </div>
    <div class="tap-outcome-title">Recent dispatch outcomes</div>
    <div id="tap-outcome-list" class="tap-outcome-list">
      <div class="skeleton sk-block" style="height:78px"></div>
      <div class="skeleton sk-block" style="height:78px"></div>
    </div>
  </div>
</div>

<!-- TAP Deal Room -->
<div class="charts-row">
  <div class="panel">
    <h3>??TAP Deal Room: Teaser to Premium Conversion</h3>
    <div id="tap-deal-room" class="tap-deal-grid">
      <div class="skeleton sk-block" style="height:180px"></div>
      <div class="skeleton sk-block" style="height:180px"></div>
    </div>
  </div>
</div>

<!-- Trends Table -->
<div class="tbl-wrap">
  <table>
    <thead><tr><th>#</th><th>키워드</th><th>바이럴</th><th>국가</th><th>가속도</th><th>인사이트</th><th>일시</th></tr></thead>
    <tbody id="t-body"></tbody>
  </table>
</div>

<div class="footer">getdaytrends Pro Dashboard — <span>Auto-refresh 30s</span> — Built with FastAPI + Chart.js</div>
<div class="toast" id="toast"></div>

<script>
// ── Color palette ──
const C = {{
  indigo: '#6366f1', violet: '#8b5cf6', green: '#22c55e',
  amber: '#f59e0b', red: '#ef4444', cyan: '#06b6d4',
  pink: '#ec4899', slate: '#64748b',
  bg: 'rgba(99,102,241,.08)',
  grid: 'rgba(148,163,184,.08)'
}};
const PALETTE = [C.indigo, C.violet, C.green, C.amber, C.cyan, C.pink, C.red, C.slate];

// ── Chart defaults ──
Chart.defaults.color = '#94a3b8';
Chart.defaults.font.family = 'Inter';
Chart.defaults.plugins.legend.labels.boxWidth = 10;

let charts = {{}};
const dashboardDegradations = new Map();
let dashboardHealthState = 'healthy';

// ── Toast notification ──
function toast(msg) {{
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 3000);
}}

function renderDashboardWarningBanner() {{
  const banner = document.getElementById('dashboard-warning-banner');
  if (!banner) return;

  const labels = [...new Set([...dashboardDegradations.values()].map(entry => entry.label).filter(Boolean))];
  if (!labels.length) {{
    banner.classList.remove('show');
    banner.innerHTML = '';
    if (dashboardHealthState === 'degraded') {{
      toast('Live dashboard data recovered.');
    }}
    dashboardHealthState = 'healthy';
    return;
  }}

  const chips = labels.map(label => `<span class="dashboard-warning-chip">${{safeHtml(label)}}</span>`).join('');
  banner.innerHTML = `
    <strong>Fallback data mode</strong>
    <div class="dashboard-warning-copy">
      <span>Some live dependencies are unavailable, so these panels are showing fallback values.</span>
      ${{chips}}
    </div>
  `;
  banner.classList.add('show');

  if (dashboardHealthState !== 'degraded') {{
    toast('Some dashboard panels are showing fallback data.');
  }}
  dashboardHealthState = 'degraded';
}}

function setDashboardDegradation(key, degraded, label, unavailableReason = '') {{
  if (!key) return;
  if (degraded) {{
    dashboardDegradations.set(key, {{ label: label || key, unavailableReason }});
  }} else {{
    dashboardDegradations.delete(key);
  }}
  renderDashboardWarningBanner();
}}

async function fetchDashboardJson(url, config = {{}}) {{
  const {{
    degradationKey = url,
    degradationLabel = 'Dashboard panel',
    options = undefined,
  }} = config;

  try {{
    const response = await fetch(url, options);
    const payload = await response.json();
    const responseMeta = payload && typeof payload === 'object' && !Array.isArray(payload) ? payload._meta : null;
    const degraded = response.headers.get('x-dashboard-degraded') === '1' || !!(responseMeta && responseMeta.degraded);
    const unavailableReason = response.headers.get('x-dashboard-degraded-reason')
      || responseMeta?.unavailable_reason
      || '';

    setDashboardDegradation(degradationKey, degraded, degradationLabel, unavailableReason);

    if (responseMeta && typeof payload === 'object' && !Array.isArray(payload)) {{
      const cleaned = {{ ...payload }};
      delete cleaned._meta;
      return cleaned;
    }}
    return payload;
  }} catch (error) {{
    setDashboardDegradation(degradationKey, true, degradationLabel, 'request_failed');
    throw error;
  }}
}}

// ── Remove skeleton ──
function reveal(id, text) {{
  const el = document.getElementById(id);
  el.classList.remove('skeleton','sk-block');
  el.textContent = text;
}}

// ── KPI + Stats loader ──
async function loadStats() {{
  const stats = await fetchDashboardJson('/api/stats', {{
    degradationKey: 'stats',
    degradationLabel: 'KPI stats',
  }});
  reveal('k-runs', stats.total_runs.toLocaleString());
  reveal('k-trends', stats.total_trends.toLocaleString());
  reveal('k-score', stats.avg_viral_score);
  reveal('k-tweets', stats.total_tweets.toLocaleString());

  const cost7 = stats.llm_cost_7d ?? 0;
  reveal('k-cost', '$' + cost7.toFixed(4));
  document.getElementById('k-cost-sub').textContent = '월 추정 $' + (cost7 / 7 * 30).toFixed(2);

  // Cost chart
  if (stats.llm_daily && stats.llm_daily.length > 0) {{
    const grouped = {{}};
    stats.llm_daily.forEach(r => {{
      if (!grouped[r.date]) grouped[r.date] = 0;
      grouped[r.date] += r.cost_usd;
    }});
    const dates = Object.keys(grouped).sort();
    const costs = dates.map(d => grouped[d]);
    renderCostChart(dates, costs);
  }}
}}

// ── Pipeline status ──
async function loadPipeline() {{
  try {{
    const ps = await fetch('/api/pipeline_status').then(r => r.json());
    const pill = document.getElementById('status-pill');
    const map = {{ idle: ['✅ 대기중','st-idle'], running: ['⚡ 실행중','st-running'], error: ['❌ 에러','st-error'] }};
    const [label, cls] = map[ps.state] || ['❓ 알수없음','st-idle'];
    pill.textContent = label;
    pill.className = 'status-pill ' + cls;
    if (ps.last_run_at) pill.title = '마지막: ' + ps.last_run_at.slice(0,16);

    const b = ps.budget || {{}};
    if (b.daily_budget_usd > 0) {{
      reveal('k-budget', '$' + (b.today_cost_usd||0).toFixed(4));
      document.getElementById('k-budget-sub').textContent = '/ $' + b.daily_budget_usd.toFixed(2);
      const pct = Math.min(b.budget_used_pct||0, 100);
      const bar = document.getElementById('k-budget-bar');
      bar.style.width = pct + '%';
      bar.className = 'budget-fill ' + (pct >= 80 ? 'bf-warn' : 'bf-ok');
    }} else {{
      reveal('k-budget', '-');
    }}
  }} catch(e) {{}}
}}

// ── Timeline chart (scatter with lines) ──
async function loadTimeline() {{
  const trends = await fetchDashboardJson('/api/trends?days=7&limit=200', {{
    degradationKey: 'timeline',
    degradationLabel: 'Trend timeline',
  }});
  if (!trends.length) return;

  const labels = trends.map(t => t.scored_at?.slice(5,16) || '');
  const scores = trends.map(t => t.viral_potential);
  const colors = scores.map(s => s >= 80 ? C.green : s >= 65 ? C.amber : C.red);

  if (charts.timeline) charts.timeline.destroy();
  charts.timeline = new Chart(document.getElementById('chart-timeline'), {{
    type: 'bar',
    data: {{
      labels,
      datasets: [{{
        label: 'Viral Score',
        data: scores,
        backgroundColor: colors.map(c => c + '40'),
        borderColor: colors,
        borderWidth: 1.5,
        borderRadius: 4
      }}]
    }},
    options: {{
      responsive: true,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ display: false }},
        y: {{ grid: {{ color: C.grid }}, beginAtZero: true, max: 100 }}
      }}
    }}
  }});

  // Table
  const tbody = document.getElementById('t-body');
  tbody.innerHTML = '';
  trends.slice(0, 50).forEach((t, i) => {{
    const s = t.viral_potential;
    const [cls, icon] = s >= 80 ? ['chip-high','🔥'] : s >= 65 ? ['chip-mid','⚡'] : ['chip-low','💤'];
    tbody.innerHTML += `<tr>
      <td>${{i+1}}</td>
      <td style="font-weight:500">${{t.keyword}}</td>
      <td><span class="chip ${{cls}}">${{icon}} ${{s}}</span></td>
      <td><span class="tag">${{t.country}}</span></td>
      <td>${{t.trend_acceleration || '-'}}</td>
      <td style="max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${{t.top_insight || '-'}}</td>
      <td style="color:#475569">${{t.scored_at?.slice(0,16) || '-'}}</td>
    </tr>`;
  }});

  // Acceleration chart (top 10)
  const sorted = [...trends].sort((a,b) => (b.trend_acceleration||0)-( a.trend_acceleration||0)).slice(0,10);
  if (charts.accel) charts.accel.destroy();
  charts.accel = new Chart(document.getElementById('chart-accel'), {{
    type: 'bar',
    data: {{
      labels: sorted.map(t => t.keyword.slice(0,12)),
      datasets: [{{
        data: sorted.map(t => t.trend_acceleration || 0),
        backgroundColor: PALETTE.map(c => c + '60'),
        borderColor: PALETTE,
        borderWidth: 1.5,
        borderRadius: 6
      }}]
    }},
    options: {{
      indexAxis: 'y',
      responsive: true,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ grid: {{ color: C.grid }} }},
        y: {{ grid: {{ display: false }} }}
      }}
    }}
  }});
}}

// ── Category pie ──
async function loadCategories() {{
  const cats = await fetchDashboardJson('/api/stats/categories?days=7', {{
    degradationKey: 'categories',
    degradationLabel: 'Category mix',
  }});
  if (!cats.length) return;

  if (charts.category) charts.category.destroy();
  charts.category = new Chart(document.getElementById('chart-category'), {{
    type: 'doughnut',
    data: {{
      labels: cats.map(c => c.category),
      datasets: [{{
        data: cats.map(c => c.count),
        backgroundColor: PALETTE.slice(0, cats.length).map(c => c + '80'),
        borderColor: PALETTE.slice(0, cats.length),
        borderWidth: 2
      }}]
    }},
    options: {{
      responsive: true,
      cutout: '60%',
      plugins: {{
        legend: {{ position: 'bottom', labels: {{ padding: 12, font: {{ size: 11 }} }} }}
      }}
    }}
  }});
}}

// ── Source quality radar ──
async function loadSourceQuality() {{
  const data = await fetchDashboardJson('/api/source/quality?days=7', {{
    degradationKey: 'source-quality',
    degradationLabel: 'Source quality',
  }});
  const sources = Object.keys(data);
  if (!sources.length) return;

  if (charts.source) charts.source.destroy();
  charts.source = new Chart(document.getElementById('chart-source'), {{
    type: 'radar',
    data: {{
      labels: sources,
      datasets: [
        {{
          label: '성공률 (%)',
          data: sources.map(s => data[s].success_rate || 0),
          borderColor: C.green,
          backgroundColor: C.green + '20',
          pointBackgroundColor: C.green
        }},
        {{
          label: '품질 점수',
          data: sources.map(s => (data[s].avg_quality_score || 0) * 100),
          borderColor: C.violet,
          backgroundColor: C.violet + '20',
          pointBackgroundColor: C.violet
        }}
      ]
    }},
    options: {{
      responsive: true,
      scales: {{
        r: {{
          beginAtZero: true, max: 100,
          grid: {{ color: C.grid }},
          pointLabels: {{ font: {{ size: 10 }} }}
        }}
      }},
      plugins: {{ legend: {{ position: 'bottom', labels: {{ font: {{ size: 10 }} }} }} }}
    }}
  }});
}}

// ── Cost bar chart ──
function renderCostChart(dates, costs) {{
  if (charts.cost) charts.cost.destroy();
  charts.cost = new Chart(document.getElementById('chart-cost'), {{
    type: 'bar',
    data: {{
      labels: dates.map(d => d.slice(5)),
      datasets: [{{
        label: 'USD',
        data: costs,
        backgroundColor: C.indigo + '60',
        borderColor: C.indigo,
        borderWidth: 1.5,
        borderRadius: 6
      }}]
    }},
    options: {{
      responsive: true,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ grid: {{ display: false }} }},
        y: {{ grid: {{ color: C.grid }}, beginAtZero: true }}
      }}
    }}
  }});
}}

// ── Logs viewer ──
async function loadLogs() {{
  try {{
    const data = await fetch('/api/logs?limit=50').then(r => r.json());
    const lv = document.getElementById('log-viewer');
    if (data.logs && data.logs.length) {{
      lv.innerHTML = data.logs.map(l => `<div>${{l.replace(/</g, '&lt;')}}</div>`).join('');
      lv.scrollTop = lv.scrollHeight;
    }} else {{
      lv.innerHTML = '<div style="color:#64748b">진행 중인 로그가 없습니다.</div>';
    }}
  }} catch(e) {{}}
}}

// ── A/B Test viewer ──
async function loadAbTest() {{
  try {{
    const data = await fetch('/api/ab_test').then(r => r.json());
    const pv = document.getElementById('ab-test-content');
    if (data.metrics) {{
      const a = data.metrics.group_a;
      const b = data.metrics.group_b;
      // Highlighting the winner
      const winA = a.conversion >= b.conversion;
      pv.innerHTML = `
        <div style="flex:1;background:rgba(99,102,241,.1);padding:16px;border-radius:8px;${{winA?'border:1px solid rgba(99,102,241,.3)':''}}">
          <div style="color:#818cf8;font-size:0.8rem;margin-bottom:8px">Control (Group A) ${{winA?'🏆':''}}</div>
          <div style="font-size:1.5rem;font-weight:700">${{a.ctr}}% <span style="font-size:0.7rem;color:#64748b;font-weight:400">CTR</span></div>
          <div style="font-size:0.85rem;color:#94a3b8;margin-top:4px">전환율: ${{a.conversion}}%</div>
        </div>
        <div style="flex:1;background:rgba(34,197,94,.1);padding:16px;border-radius:8px;${{!winA?'border:1px solid rgba(34,197,94,.3)':''}}">
          <div style="color:#22c55e;font-size:0.8rem;margin-bottom:8px">Variant (Group B) ${{!winA?'🏆':''}}</div>
          <div style="font-size:1.5rem;font-weight:700;color:#f1f5f9">${{b.ctr}}% <span style="font-size:0.7rem;color:#64748b;font-weight:400">CTR</span></div>
          <div style="font-size:0.85rem;color:#94a3b8;margin-top:4px">전환율: ${{b.conversion}}%</div>
        </div>
      `;
    }}
  }} catch(e) {{}}
}}

// ── Init ──
function getTapTargetCountry() {{
  return (document.getElementById('tap-target-country')?.value || '').trim().toLowerCase();
}}

function getTapAlertLifecycle() {{
  return (document.getElementById('tap-alert-lifecycle')?.value || '').trim().toLowerCase();
}}

function getTapAlertLimit() {{
  const value = parseInt(document.getElementById('tap-alert-limit')?.value || '6', 10);
  return Number.isFinite(value) && value > 0 ? value : 6;
}}

function buildTapQuery(params) {{
  const query = new URLSearchParams();
  Object.entries(params || {{}}).forEach(([key, value]) => {{
    if (value === undefined || value === null || value === '') return;
    query.set(key, String(value));
  }});
  return query.toString();
}}

const TAP_PRESET_STORAGE_KEY = 'getdaytrends.tap-target-presets';

function normalizeTapPreset(value) {{
  return String(value || '').trim().toLowerCase();
}}

function getDefaultTapPresets() {{
  return ['', 'korea', 'united-states', 'japan'];
}}

function dedupeTapPresets(values) {{
  const seen = new Set();
  const normalized = [];
  values.forEach(value => {{
    const candidate = normalizeTapPreset(value);
    if (seen.has(candidate)) return;
    seen.add(candidate);
    normalized.push(candidate);
  }});
  if (!seen.has('')) normalized.unshift('');
  return normalized.slice(0, 8);
}}

function readTapPresets() {{
  try {{
    const raw = localStorage.getItem(TAP_PRESET_STORAGE_KEY);
    if (!raw) return dedupeTapPresets(getDefaultTapPresets());
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return dedupeTapPresets(getDefaultTapPresets());
    return dedupeTapPresets(parsed);
  }} catch(e) {{
    return dedupeTapPresets(getDefaultTapPresets());
  }}
}}

function writeTapPresets(presets) {{
  try {{
    localStorage.setItem(TAP_PRESET_STORAGE_KEY, JSON.stringify(dedupeTapPresets(presets)));
  }} catch(e) {{}}
}}

function renderTapPresetStrip() {{
  const container = document.getElementById('tap-preset-strip');
  if (!container) return;
  const activeCountry = getTapTargetCountry();
  const presets = readTapPresets();
  container.innerHTML = presets.map(value => {{
    const label = value ? safeHtml(value.toUpperCase()) : 'ALL';
    const activeCls = value === activeCountry ? ' tap-preset-btn-active' : '';
    return `<button class="tap-preset-btn${{activeCls}}" onclick="applyTapPreset('${{safeHtml(value)}}')">${{label}}</button>`;
  }}).join('');
}}

function rememberTapPreset(value) {{
  const candidate = normalizeTapPreset(value);
  if (!candidate) return;
  writeTapPresets([candidate, ...readTapPresets()]);
  renderTapPresetStrip();
}}

function applyTapPreset(value = '') {{
  const input = document.getElementById('tap-target-country');
  if (!input) return;
  input.value = normalizeTapPreset(value);
  renderTapPresetStrip();
  syncTapOpsView();
}}

function saveCurrentTapPreset() {{
  const current = getTapTargetCountry();
  if (!current) {{
    toast('Enter a market before saving a preset.');
    return;
  }}
  rememberTapPreset(current);
  toast(`Saved preset for ${{current.toUpperCase()}}.`);
}}

function resetTapPresets() {{
  writeTapPresets(getDefaultTapPresets());
  renderTapPresetStrip();
  toast('Preset markets reset.');
}}

function getTapDealRoomSessionId() {{
  const storageKey = 'getdaytrends.tap-session-id';
  try {{
    let sessionId = localStorage.getItem(storageKey);
    if (!sessionId) {{
      sessionId = (window.crypto && typeof window.crypto.randomUUID === 'function')
        ? window.crypto.randomUUID()
        : `tap-${{Date.now().toString(36)}}-${{Math.random().toString(36).slice(2, 10)}}`;
      localStorage.setItem(storageKey, sessionId);
    }}
    return sessionId;
  }} catch (e) {{
    return `tap-${{Date.now().toString(36)}}`;
  }}
}}

function getTapDealRoomImpressionKey(room, offer) {{
  return [
    'tap-deal-room',
    room.snapshot_id || 'snapshot',
    room.target_country || 'global',
    room.audience_segment || 'creator',
    offer.keyword || 'unknown',
    offer.tier || 'premium',
  ].join(':').toLowerCase();
}}

function formatTapPct(value) {{
  return `${{(Number(value || 0) * 100).toFixed(1)}}%`;
}}

function formatTapMoney(value) {{
  return `$${{Number(value || 0).toFixed(0)}}`;
}}

async function trackTapDealRoomEvent({{ room, offer, eventType, revenueValue = 0 }}) {{
  try {{
    const params = new URLSearchParams();
    const payload = {{
      keyword: offer.keyword || '',
      event_type: eventType || '',
      snapshot_id: room.snapshot_id || '',
      target_country: room.target_country || getTapTargetCountry(),
      audience_segment: room.audience_segment || 'creator',
      package_tier: room.package_tier || 'premium_alert_bundle',
      offer_tier: offer.tier || 'premium',
      price_anchor: offer.price_anchor || '',
      checkout_handle: offer.checkout_handle || '',
      session_id: getTapDealRoomSessionId(),
      actor_id: 'dashboard',
      revenue_value: String(revenueValue || 0),
    }};
    Object.entries(payload).forEach(([key, value]) => {{
      if (value !== undefined && value !== null && String(value).length) {{
        params.set(key, String(value));
      }}
    }});
    await fetch(`/api/tap/deal-room/events?${{params.toString()}}`, {{ method: 'POST' }});
  }} catch (e) {{}}
}}

async function trackTapDealRoomImpressions(room) {{
  const tracked = [];
  (room.offers || []).forEach(offer => {{
    const key = getTapDealRoomImpressionKey(room, offer);
    try {{
      if (!sessionStorage.getItem(key)) {{
        sessionStorage.setItem(key, getTapDealRoomSessionId());
        tracked.push(trackTapDealRoomEvent({{ room, offer, eventType: 'view' }}));
      }}
    }} catch (e) {{
      tracked.push(trackTapDealRoomEvent({{ room, offer, eventType: 'view' }}));
    }}
  }});
  if (tracked.length) {{
    await Promise.allSettled(tracked);
  }}
}}

async function openTapDealRoomCheckout(room, offer) {{
  const response = await fetch('/api/tap/deal-room/checkout', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify({{
      keyword: offer.keyword || '',
      snapshot_id: room.snapshot_id || '',
      target_country: room.target_country || getTapTargetCountry(),
      audience_segment: room.audience_segment || 'creator',
      package_tier: offer.package_tier || room.package_tier || 'premium_alert_bundle',
      offer_tier: offer.tier || 'premium',
      price_anchor: offer.price_anchor || '',
      quoted_price_value: Number(offer.price_value || 0),
      premium_title: offer.premium_title || offer.keyword || '',
      teaser_body: offer.teaser_body || '',
      checkout_handle: offer.checkout_handle || '',
      currency: 'usd',
      actor_id: getTapDealRoomSessionId(),
      pricing_variant: offer.pricing_variant || '',
      pricing_context: offer.pricing_context || {{}},
    }}),
  }});
  const payload = await response.json().catch(() => ({{}}));
  if (!response.ok) {{
    throw new Error(payload.error || 'Checkout is unavailable');
  }}
  if (!payload.url) {{
    throw new Error('Stripe checkout URL is missing');
  }}
  window.location.assign(payload.url);
}}

function bindTapDealRoomActions(room) {{
  document.querySelectorAll('[data-tap-offer-index]').forEach(node => {{
    node.addEventListener('click', async () => {{
      const offerIndex = Number(node.getAttribute('data-tap-offer-index') || '-1');
      const offer = (room.offers || [])[offerIndex];
      if (!offer) return;
      node.disabled = true;
      try {{
        await trackTapDealRoomEvent({{ room, offer, eventType: 'click' }});
        if (offer.checkout_handle) {{
          await openTapDealRoomCheckout(room, offer);
          return;
        }}
        toast(`Offer click tracked for ${{offer.keyword}}.`);
      }} catch (e) {{
        toast(e && e.message ? e.message : `Checkout unavailable for ${{offer.keyword}}.`);
      }} finally {{
        node.disabled = false;
      }}
    }});
  }});
}}

function handleTapCheckoutStateFromUrl() {{
  try {{
    const params = new URLSearchParams(window.location.search);
    const state = params.get('tap_checkout');
    const keyword = params.get('tap_keyword');
    if (!state) return;
    if (state === 'success') {{
      toast(keyword ? `Purchase completed for ${{keyword}}.` : 'Purchase completed.');
      loadTapDealRoom();
    }} else if (state === 'cancel') {{
      toast(keyword ? `Checkout canceled for ${{keyword}}.` : 'Checkout canceled.');
    }}
    params.delete('tap_checkout');
    params.delete('tap_keyword');
    const query = params.toString();
    const nextUrl = `${{window.location.pathname}}${{query ? `?${{query}}` : ''}}${{window.location.hash || ''}}`;
    window.history.replaceState({{}}, '', nextUrl);
  }} catch (e) {{}}
}}

async function loadTapBoard() {{
  try {{
    const board = document.getElementById('tap-board');
    const targetCountry = getTapTargetCountry();
    const query = buildTapQuery({{ limit: 6, teaser_count: 2, target_country: targetCountry }});
    const data = await fetchDashboardJson(`/api/tap/opportunities?${{query}}`, {{
      degradationKey: 'tap-board',
      degradationLabel: 'TAP opportunities',
    }});
    if (!data.items || !data.items.length) {{
      const scope = targetCountry ? ` for ${{safeHtml(targetCountry.toUpperCase())}}` : '';
      board.innerHTML = `
        <div class="tap-card">
          <div class="tap-title">No live arbitrage slots${{scope}}</div>
          <div class="tap-copy">Cross-country divergence is quiet right now. The board will refill when a market gap opens.</div>
        </div>
      `;
      return;
    }}

    board.innerHTML = data.items.map(item => {{
      const badgeCls = item.paywall_tier === 'free_teaser' ? 'tap-free' : 'tap-premium';
      const badgeLabel = item.paywall_tier === 'free_teaser' ? 'Free teaser' : 'Premium';
      const platforms = (item.recommended_platforms || []).map(p => `<span class="tap-chip">${{safeHtml(p)}}</span>`).join('');
      const targets = (item.target_countries || []).map(c => safeHtml(String(c).toUpperCase())).join(', ');
      const notes = (item.execution_notes || []).slice(0, 2).map(note => `<div>${{safeHtml(note)}}</div>`).join('');
      const windowText = item.publish_window
        ? `${{item.publish_window.urgency_label}} · closes in ${{item.publish_window.closes_in_minutes}}m`
        : 'window pending';

      return `
        <div class="tap-card">
          <div class="tap-head">
            <div class="tap-title">${{safeHtml(item.keyword)}}</div>
            <div class="tap-badge ${{badgeCls}}">${{badgeLabel}}</div>
          </div>
          <div class="tap-meta">
            <span class="tap-chip">score ${{item.viral_score}}</span>
            <span class="tap-chip">priority ${{item.priority}}</span>
            <span class="tap-chip">${{item.source_country.toUpperCase()}} → ${{targets || 'GLOBAL'}}</span>
          </div>
          <div class="tap-copy">${{safeHtml(item.public_teaser || item.recommended_angle || '')}}</div>
          <div class="tap-copy" style="font-size:.78rem;color:#a5b4fc;">${{platforms}}</div>
          <div class="tap-notes">${{notes}}</div>
          <div class="tap-lock">${{windowText}}</div>
        </div>
      `;
    }}).join('');
  }} catch(e) {{}}
}}

async function loadTapDealRoom() {{
  const container = document.getElementById('tap-deal-room');
  if (!container) return;
  try {{
    const targetCountry = getTapTargetCountry();
    const roomQuery = buildTapQuery({{
      limit: 4,
      teaser_count: 2,
      target_country: targetCountry,
      audience_segment: 'creator',
      include_checkout: 'true',
    }});
    const funnelQuery = buildTapQuery({{
      days: 30,
      limit: 8,
      target_country: targetCountry,
      audience_segment: 'creator',
      package_tier: 'premium_alert_bundle',
    }});
    const checkoutQuery = buildTapQuery({{
      days: 30,
      limit: 4,
      target_country: targetCountry,
      audience_segment: 'creator',
      package_tier: 'premium_alert_bundle',
    }});
    const [data, funnel, checkoutSummary] = await Promise.all([
      fetchDashboardJson(`/api/tap/deal-room?${{roomQuery}}`, {{
        degradationKey: 'tap-deal-room',
        degradationLabel: 'TAP deal room',
      }}),
      fetchDashboardJson(`/api/tap/deal-room/funnel?${{funnelQuery}}`, {{
        degradationKey: 'tap-deal-room-funnel',
        degradationLabel: 'TAP deal room',
      }}).catch(() => null),
      fetchDashboardJson(`/api/tap/deal-room/checkouts?${{checkoutQuery}}`, {{
        degradationKey: 'tap-deal-room-checkouts',
        degradationLabel: 'TAP deal room',
      }}).catch(() => null),
    ]);
    if (!data.offers || !data.offers.length) {{
      const scope = targetCountry ? ` for ${{safeHtml(targetCountry.toUpperCase())}}` : '';
      container.innerHTML = `
        <div class="tap-deal-card">
          <div class="tap-title">No monetizable bundle ready${{scope}}</div>
          <div class="tap-copy">When the next arbitrage gap opens, this room will package a teaser lane and a premium conversion lane automatically.</div>
        </div>
      `;
      return;
    }}

    const totals = funnel && funnel.totals ? funnel.totals : null;
    const checkoutTotals = checkoutSummary && checkoutSummary.totals ? checkoutSummary.totals : null;
    const summaryCard = totals ? `
      <div class="tap-deal-card" style="grid-column:1 / -1;">
        <div class="tap-title">Conversion learning loop</div>
        <div class="tap-copy">Recent deal-room behavior is now feeding the ranking layer for each offer lane.</div>
        <div class="tap-summary">
          <div class="tap-summary-card">
            <div class="tap-summary-label">Views</div>
            <div class="tap-summary-value">${{safeHtml(String(totals.views || 0))}}</div>
          </div>
          <div class="tap-summary-card">
            <div class="tap-summary-label">CTR</div>
            <div class="tap-summary-value">${{safeHtml(formatTapPct(totals.ctr || 0))}}</div>
          </div>
          <div class="tap-summary-card">
            <div class="tap-summary-label">Purchases</div>
            <div class="tap-summary-value">${{safeHtml(String(totals.purchases || 0))}}</div>
          </div>
          <div class="tap-summary-card">
            <div class="tap-summary-label">Revenue</div>
            <div class="tap-summary-value">${{safeHtml(formatTapMoney(totals.revenue || 0))}}</div>
          </div>
        </div>
      </div>
    ` : '';
    const checkoutCard = checkoutTotals ? `
      <div class="tap-deal-card" style="grid-column:1 / -1;">
        <div class="tap-title">Checkout ops</div>
        <div class="tap-copy">Stripe session creation and purchase completion are now tracked separately for pricing and drop-off analysis.</div>
        <div class="tap-summary">
          <div class="tap-summary-card">
            <div class="tap-summary-label">Created</div>
            <div class="tap-summary-value">${{safeHtml(String(checkoutTotals.created || 0))}}</div>
          </div>
          <div class="tap-summary-card">
            <div class="tap-summary-label">Completed</div>
            <div class="tap-summary-value">${{safeHtml(String(checkoutTotals.completed || 0))}}</div>
          </div>
          <div class="tap-summary-card">
            <div class="tap-summary-label">Close rate</div>
            <div class="tap-summary-value">${{safeHtml(formatTapPct(checkoutTotals.completion_rate || 0))}}</div>
          </div>
          <div class="tap-summary-card">
            <div class="tap-summary-label">Captured</div>
            <div class="tap-summary-value">${{safeHtml(formatTapMoney(checkoutTotals.captured_revenue || 0))}}</div>
          </div>
        </div>
      </div>
    ` : '';

    container.innerHTML = summaryCard + checkoutCard + data.offers.map((offer, index) => {{
      const outline = (offer.bundle_outline || [])
        .slice(0, 4)
        .map(item => `<div class="tap-outline-item">${{safeHtml(item)}}</div>`)
        .join('');
      const sponsorFit = (offer.sponsor_fit || [])
        .slice(0, 4)
        .map(item => `<span class="tap-chip">${{safeHtml(item)}}</span>`)
        .join('');
      const funnelStats = offer.funnel_stats || {{}};
      const pricingContext = offer.pricing_context || {{}};
      const learningNote = offer.learning_note
        ? `<div class="tap-notes">${{safeHtml(offer.learning_note)}}</div>`
        : '';
      return `
        <div class="tap-deal-card">
          <div class="tap-deal-top">
            <div>
              <div class="tap-title">${{safeHtml(offer.teaser_headline || offer.keyword)}}</div>
              <div class="tap-lock">${{safeHtml(offer.tier)}} lane</div>
            </div>
            <div class="tap-price">${{safeHtml(offer.price_anchor || '$0')}}</div>
          </div>
          <div class="tap-copy">${{safeHtml(offer.teaser_body || '')}}</div>
          <div class="tap-copy" style="font-size:.78rem;color:#f8fafc;">${{safeHtml(offer.premium_title || '')}}</div>
          <div class="tap-meta">${{sponsorFit}}</div>
          <div class="tap-meta">
            <span class="tap-chip">views ${{safeHtml(String(funnelStats.views || 0))}}</span>
            <span class="tap-chip">ctr ${{safeHtml(formatTapPct(funnelStats.ctr || 0))}}</span>
            <span class="tap-chip">purchases ${{safeHtml(String(funnelStats.purchases || 0))}}</span>
            <span class="tap-chip">pricing ${{safeHtml(String(pricingContext.experiment_strategy || 'baseline'))}}</span>
          </div>
          <div class="tap-outline">${{outline}}</div>
          ${{learningNote}}
          <div class="tap-actions">
            <button type="button" class="tap-btn" data-tap-offer-index="${{index}}">${{safeHtml(offer.cta_label || 'Open bundle')}}</button>
          </div>
        </div>
      `;
    }}).join('');
    await trackTapDealRoomImpressions(data);
    bindTapDealRoomActions(data);
  }} catch(e) {{
    container.innerHTML = `
      <div class="tap-deal-card">
        <div class="tap-title">Deal room unavailable</div>
        <div class="tap-copy">The dashboard could not load the monetization view right now.</div>
      </div>
    `;
  }}
}}

function renderFastViral(data) {{
  const container = document.getElementById('fast-viral-list');
  const status = document.getElementById('fast-viral-status');
  if (!container || !status) return;
  const items = Array.isArray(data.items) ? data.items : [];
  const sourceHealth = data.source_health || {{}};
  const fallbackMode = Boolean(data.fallback_mode);
  const exclusions = data.excluded_topic_counts || {{}};
  const excludedTotal = Object.values(exclusions).reduce((sum, value) => sum + Number(value || 0), 0);
  const refreshed = data.refreshed_at ? new Date(data.refreshed_at).toLocaleString('ko-KR') : '-';
  status.innerHTML = `
    <span class="live-dot"></span>
    <strong>${{items.length}}개 커뮤니티 원문</strong>
    <span class="fast-viral-early">${{safeHtml(String(data.community_source_count || 0))}}개 출처 · 실측 선행 ${{safeHtml(String(data.measured_lead_count || 0))}}건</span>
    <span>직접 목록 ${{safeHtml(String(data.direct_source_count || 0))}}/4곳 연결 · 직접 표시 ${{safeHtml(String(data.direct_displayed_count || 0))}}건 · 원문 이동 ${{safeHtml(String(data.resolved_original_count || 0))}}건</span>
    <span>스포츠·정치·증시·실적·부동산 ${{safeHtml(String(excludedTotal))}}건 제외</span>
    <span>갱신 ${{safeHtml(refreshed)}}</span>
  `;
  if (!items.length) {{
    const errors = Array.isArray(data.errors) && data.errors.length ? ` (${{safeHtml(data.errors.join(', '))}})` : '';
    container.innerHTML = `<div class="x-radar-empty">현재 속도·안전 게이트를 통과한 조기 후보가 없습니다.${{errors}} 2분 뒤 다시 확인합니다.</div>`;
    return;
  }}
  container.innerHTML = items.map((item, index) => {{
    const firstSeen = item.first_seen_at ? new Date(item.first_seen_at).toLocaleTimeString('ko-KR', {{hour:'2-digit', minute:'2-digit', second:'2-digit'}}) : '이번 수집에서 확인';
    const leadLabel = item.lead_status === 'measured'
      ? `실측 선행 ${{safeHtml(String(item.lead_minutes))}}분`
      : (item.lead_status === 'awaiting_aggregator' ? 'IssueLink 등장 대기' : (item.lead_status === 'same_poll' ? '동일 수집 주기 감지' : 'IssueLink 최초 감지'));
    const scoreBlock = Number.isFinite(item.x_exposure_score)
      ? `<div class="fast-viral-score">${{safeHtml(String(item.x_exposure_score))}}<small>X 적합도</small></div>`
      : '<div class="fast-viral-score"><small>집계 확인</small></div>';
    const exposureReasons = (item.exposure_reasons || [])
      .map(reason => `<span class="x-radar-reason">${{safeHtml(reason)}}</span>`)
      .join('');
    const confidenceLabel = ({{high: '높음', medium: '중간', low: '낮음'}})[item.exposure_confidence] || '미산정';
    const originLabel = item.link_kind === 'publisher_original' ? '원문' : '원문 이동';
    return `
      <article class="fast-viral-card">
        <div class="x-radar-card-top">
          <div>
            <div class="reference-connector-note">#${{index + 1}} · ${{safeHtml(item.community_label || item.community_source || '커뮤니티')}} · 최초 감지 ${{safeHtml(firstSeen)}} · ${{safeHtml(leadLabel)}} · 근거 신뢰도 ${{safeHtml(confidenceLabel)}} · ${{safeHtml(item.score_version || '기존 점수')}}</div>
            <div class="x-radar-keyword"><a href="${{safeExternalUrl(item.source_url)}}" target="_blank" rel="noopener noreferrer" style="color:inherit;text-decoration:none">${{safeHtml(item.title)}} ↗</a></div>
          </div>
          ${{scoreBlock}}
        </div>
        <div class="x-radar-reasons">
          ${{exposureReasons}}
          ${{item.views ? `<span class="x-radar-reason">조회 ${{safeHtml(Number(item.views).toLocaleString())}}</span>` : ''}}
          ${{item.views_per_minute != null ? `<span class="x-radar-reason">분당 ${{safeHtml(String(item.views_per_minute))}}</span>` : ''}}
          <span class="x-radar-reason">댓글 ${{safeHtml(String(item.comments || 0))}}</span>
          ${{item.votes ? `<span class="x-radar-reason">추천 ${{safeHtml(String(item.votes))}}</span>` : ''}}
          <span class="x-radar-reason">${{safeHtml(item.issuelink_status || '')}}</span>
        </div>
        <div class="x-radar-actions">
          <a class="x-radar-link" href="${{safeExternalUrl(item.source_url)}}" target="_blank" rel="noopener noreferrer">${{safeHtml(item.community_label || '커뮤니티')}} ${{originLabel}} ↗</a>
          <a class="x-radar-link" href="${{safeExternalUrl(item.x_search_url)}}" target="_blank" rel="noopener noreferrer">X 검색 ↗</a>
          <a class="x-radar-link" href="${{safeExternalUrl(item.threads_search_url)}}" target="_blank" rel="noopener noreferrer">Threads 검색 ↗</a>
        </div>
      </article>
    `;
  }}).join('');
}}

async function refreshFastViral(silent = false) {{
  const button = document.getElementById('fast-viral-refresh');
  const status = document.getElementById('fast-viral-status');
  if (!button || !status) return;
  button.disabled = true;
  status.innerHTML = '<span class="live-dot"></span><span>여러 커뮤니티 원문과 실제 최초 감지 시각을 확인하고 있습니다…</span>';
  try {{
    const limit = Number(document.getElementById('fast-viral-limit')?.value || 12);
    const response = await fetch(`/api/fast-viral/refresh?limit=${{limit}}`, {{ method: 'POST' }});
    if (!response.ok) throw new Error('fast_viral_refresh_failed');
    const data = await response.json();
    renderFastViral(data);
    if (!silent) toast(`조기 후보 ${{(data.items || []).length}}개를 확인했습니다.`);
  }} catch (error) {{
    status.innerHTML = '<span class="live-dot"></span><span>커뮤니티 조기감지 실패 — 잠시 후 다시 시도해 주세요.</span>';
  }} finally {{
    button.disabled = false;
  }}
}}

function getXRadarFocusKeywords() {{
  const raw = document.getElementById('x-radar-focus')?.value || '';
  return raw.split(',').map(value => value.trim()).filter(Boolean).slice(0, 8);
}}

function safeExternalUrl(value) {{
  const url = String(value || '');
  const normalized = url.toLowerCase();
  return normalized.startsWith('https://') || normalized.startsWith('http://') ? safeHtml(url) : '#';
}}

function renderXRadar(data) {{
  const container = document.getElementById('x-radar-list');
  const status = document.getElementById('x-radar-status');
  if (!container || !status) return;
  const items = Array.isArray(data.items) ? data.items : [];
  const sourceHealth = data.source_health || {{}};
  const refreshed = data.refreshed_at ? new Date(data.refreshed_at).toLocaleString('ko-KR') : '-';
  const sourceLabels = [
    sourceHealth.google_trends ? 'Google 실시간 검색 연결' : 'Google 실시간 검색 미응답',
    sourceHealth.public_x_trends ? '공개 X 트렌드 연결' : '공개 X 트렌드 미응답',
    sourceHealth.publisher_news_origins ? '게시사 원문·시각 확대 연결' : '게시사 원문 확대 미응답',
    sourceHealth.threads_api ? 'Threads 공식 검색 연결' : 'Threads 수동 검색 링크',
  ];
  const exclusions = data.filter_summary || {{}};
  const excludedTopicCount = Number(exclusions['스포츠 제외'] || 0)
    + Number(exclusions['정치 제외'] || 0)
    + Number(exclusions['증시·실적 제외'] || 0)
    + Number(exclusions['부동산 제외'] || 0);
  const errorText = (data.errors || []).length
    ? `<span class="reference-connector-note">일부 소스 오류 ${{data.errors.length}}건</span>`
    : '';
  status.innerHTML = `
    <span class="live-dot"></span>
    <strong>${{items.length}}개 원문 소재</strong>
    <span>X 노출 적합도 순 · X 네이티브 ${{safeHtml(String(data.x_native_count || 0))}}개</span>
    <span>스포츠·정치·증시·실적·부동산 ${{safeHtml(String(excludedTopicCount))}}개 제외 · 기타 근거 부족 ${{safeHtml(String(Math.max(0, Number(data.filtered_out_count || 0) - excludedTopicCount)))}}개</span>
    <span>${{safeHtml(sourceLabels.join(' · '))}}</span>
    <span>갱신 ${{safeHtml(refreshed)}}</span>
    ${{errorText}}
  `;

  if (!items.length) {{
    container.innerHTML = '<div class="x-radar-empty">현재 소재성 게이트를 통과한 주제가 없습니다. 독립 원문 또는 Threads 교차 근거가 생기면 표시됩니다.</div>';
    return;
  }}

  container.innerHTML = items.map((item, index) => {{
    const sourceLinks = (item.news_items || [])
      .filter(article => article && article.url)
      .slice(0, 6)
      .map(article => `
        <a class="x-radar-source" href="${{safeExternalUrl(article.url)}}" target="_blank" rel="noopener noreferrer">
          <div class="x-radar-source-name">${{article.is_first_report ? '수집 원문 중 최초 · ' : ''}}${{safeHtml(article.source || '언론사 원문')}}${{article.published_at ? ' · ' + safeHtml(new Date(article.published_at).toLocaleString('ko-KR')) : ''}} · 원문 열기 ↗</div>
          <div class="x-radar-source-title">${{safeHtml(article.title || item.keyword)}}</div>
        </a>
      `).join('');
    const reasons = [...(item.exposure_signals || []), ...(item.reasons || [])]
      .filter((reason, reasonIndex, allReasons) => allReasons.indexOf(reason) === reasonIndex)
      .map(reason => `<span class="x-radar-reason">${{safeHtml(reason)}}</span>`).join('');
    const threadsLinks = (item.threads_posts || [])
      .filter(post => post && post.permalink)
      .slice(0, 3)
      .map(post => `
        <a class="x-radar-source" href="${{safeExternalUrl(post.permalink)}}" target="_blank" rel="noopener noreferrer">
          <div class="x-radar-source-name">Threads · @${{safeHtml(post.username || '작성자')}} · 원문 열기 ↗</div>
          <div class="x-radar-source-title">${{safeHtml(post.text || item.keyword)}}</div>
        </a>
      `).join('');
    const ageLabel = Number.isFinite(item.age_minutes) ? `${{item.age_minutes}}분 전` : '현재 트렌드';
    const confidenceLabel = ({{high: '높음', medium: '중간', low: '낮음'}})[item.exposure_confidence] || '미산정';
    const originals = sourceLinks + threadsLinks || (item.qualification_mode === 'x_native_history'
      ? '<div class="reference-connector-note">뉴스 맥락 미확인 — 공개 X 트렌드 원문 페이지와 X 실시간 검색에서 확인하세요.</div>'
      : '<div class="reference-connector-note">연결된 원문 없음 — X·Threads 검색에서 맥락을 확인하세요.</div>');
    return `
      <article class="x-radar-card">
        <div class="x-radar-card-top">
          <div>
            <div class="reference-connector-note">#${{index + 1}} · ${{safeHtml(item.lane)}} · ${{safeHtml(ageLabel)}}</div>
            <div class="x-radar-keyword">${{safeHtml(item.keyword)}}</div>
            <div class="tap-meta" style="margin-top:8px">
              <span class="tap-chip">${{safeHtml(item.category)}}</span>
              <span class="tap-chip">검색량 ${{safeHtml(item.volume || 'N/A')}}</span>
              <span class="tap-chip">${{safeHtml((item.sources || []).join(' + '))}}</span>
              <span class="tap-chip">근거 신뢰도 ${{safeHtml(confidenceLabel)}} · ${{safeHtml(item.score_version || '기존 점수')}}</span>
            </div>
          </div>
          <div class="x-radar-score">${{safeHtml(String(item.x_exposure_score ?? item.materiality_score ?? item.opportunity_score))}}<small>X 적합도</small></div>
        </div>
        <div class="x-radar-reasons">${{reasons}}</div>
        <div class="x-radar-sources">${{originals}}</div>
        <div class="x-radar-actions">
          <a class="x-radar-link" href="${{safeExternalUrl(item.x_search_url)}}" target="_blank" rel="noopener noreferrer">X 실시간 검색 ↗</a>
          <a class="x-radar-link" href="${{safeExternalUrl(item.threads_search_url)}}" target="_blank" rel="noopener noreferrer">Threads 검색 ↗</a>
          ${{item.trend_url ? `<a class="x-radar-link" href="${{safeExternalUrl(item.trend_url)}}" target="_blank" rel="noopener noreferrer">트렌드 출처 ↗</a>` : ''}}
        </div>
      </article>
    `;
  }}).join('');
}}

async function refreshXRadar(silent = false) {{
  const button = document.getElementById('x-radar-refresh');
  const status = document.getElementById('x-radar-status');
  if (!button || !status) return;
  button.disabled = true;
  status.innerHTML = '<span class="live-dot"></span><span>최신 검색 급등과 공개 X 트렌드에서 원문을 확인하고 있습니다…</span>';
  try {{
    const response = await fetch('/api/x-radar/refresh', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{
        country: 'korea',
        limit: Number(document.getElementById('x-radar-limit')?.value || 20),
        focus_keywords: getXRadarFocusKeywords(),
        force_refresh: !silent,
      }}),
    }});
    if (!response.ok) throw new Error('x_radar_refresh_failed');
    const data = await response.json();
    renderXRadar(data);
    if (!silent) toast(`원문 소재 ${{(data.items || []).length}}개를 새로 확인했습니다.`);
  }} catch (error) {{
    status.innerHTML = '<span class="live-dot"></span><span>원문 레이더 갱신 실패 — 잠시 후 다시 시도해 주세요.</span>';
  }} finally {{
    button.disabled = false;
  }}
}}

function getLiveReferenceKeywords() {{
  const raw = document.getElementById('reference-live-keywords')?.value || '';
  return raw.split(',').map(value => value.trim()).filter(Boolean).slice(0, 5);
}}

async function refreshLiveReferences(silent = false) {{
  const button = document.getElementById('reference-live-refresh');
  const status = document.getElementById('reference-live-status');
  if (!button || !status) return;
  button.disabled = true;
  status.innerHTML = '<span class="live-dot"></span><span>YouTube에서 최신 콘텐츠를 수집하고 있습니다…</span>';
  try {{
    const response = await fetch('/api/reference-library/live/refresh', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{
        keywords: getLiveReferenceKeywords(),
        per_keyword: Number(document.getElementById('reference-live-limit')?.value || 5),
      }}),
    }});
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'live_refresh_failed');
    const refreshedAt = data.refreshed_at ? new Date(data.refreshed_at).toLocaleTimeString('ko-KR') : '방금';
    const errorText = (data.errors || []).length
      ? `<span class="reference-connector-note">일부 오류 ${{data.errors.length}}건</span>`
      : '';
    status.innerHTML = `
      <span class="live-dot"></span>
      <strong>YouTube LIVE</strong>
      <span>${{data.collected || 0}}개 확인 · 신규 ${{data.created || 0}} · 갱신 ${{data.updated || 0}} · ${{refreshedAt}}</span>
      ${{errorText}}
      <span class="reference-connector-note">Instagram · TikTok · Threads · X는 공식 API 필요</span>
    `;
    await loadReferenceLibrary();
    if (!silent) toast(`라이브 콘텐츠 ${{data.collected || 0}}개를 반영했습니다.`);
  }} catch (error) {{
    status.innerHTML = `
      <span class="live-dot"></span>
      <span>라이브 수집 실패: ${{safeHtml(error.message || '연결 오류')}}</span>
      <span class="reference-connector-note">잠시 후 다시 시도해 주세요.</span>
    `;
    if (!silent) toast('라이브 수집에 실패했습니다.');
  }} finally {{
    button.disabled = false;
  }}
}}

async function loadReferenceLibrary() {{
  const container = document.getElementById('reference-list');
  const statsContainer = document.getElementById('reference-stats');
  if (!container || !statsContainer) return;

  const params = new URLSearchParams();
  const query = document.getElementById('reference-query')?.value.trim() || '';
  const platform = document.getElementById('reference-platform-filter')?.value || '';
  const state = document.getElementById('reference-state-filter')?.value || '';
  if (query) params.set('q', query);
  if (platform) params.set('platform', platform);
  if (state === 'saved') params.set('saved', 'true');
  if (state === 'unread') params.set('read', 'false');
  if (state === 'recommended') params.set('min_score', '80');

  try {{
    const [listResponse, statsResponse] = await Promise.all([
      fetch(`/api/reference-library?${{params.toString()}}`),
      fetch('/api/reference-library/stats'),
    ]);
    if (!listResponse.ok || !statsResponse.ok) throw new Error('reference_library_unavailable');
    const data = await listResponse.json();
    const stats = await statsResponse.json();
    const platformStats = Object.entries(stats.by_platform || {{}})
      .map(([name, count]) => `<span class="tap-chip">${{safeHtml(name)}} ${{count}}</span>`)
      .join('');
    statsContainer.innerHTML = `
      <span class="tap-chip">전체 ${{stats.total || 0}}</span>
      <span class="tap-chip">즐겨찾기 ${{stats.saved || 0}}</span>
      <span class="tap-chip">안 읽음 ${{stats.unread || 0}}</span>
      <span class="tap-chip">추천 ${{stats.recommended || 0}}</span>
      ${{platformStats}}
    `;

    const items = data.items || [];
    if (!items.length) {{
      container.innerHTML = `
        <div class="reference-card">
          <div class="reference-title">아직 맞는 레퍼런스가 없습니다.</div>
          <div class="reference-copy">원본 URL과 제목을 추가하면 추천 점수 순으로 정리됩니다.</div>
        </div>
      `;
      return;
    }}

    container.innerHTML = items.map(item => {{
      const scoreClass = item.recommendation_score >= 80 ? 'chip-high' : (item.recommendation_score >= 60 ? 'chip-mid' : 'chip-low');
      const preview = item.summary || item.caption || item.translated_text || '요약을 아직 기록하지 않았습니다.';
      const transcriptBlock = item.transcript
        ? `<div class="reference-copy"><strong>대본</strong>\n${{safeHtml(item.transcript)}}</div>`
        : '';
      const translationBlock = item.translated_text
        ? `<div class="reference-copy"><strong>번역</strong>\n${{safeHtml(item.translated_text)}}</div>`
        : '';
      return `
        <article class="reference-card">
          <div class="reference-card-top">
            <div>
              <div class="reference-title"><a href="${{safeHtml(item.source_url)}}" target="_blank" rel="noopener noreferrer">${{safeHtml(item.title)}}</a></div>
              <div class="tap-meta" style="margin-top:8px">
                <span class="tap-chip">${{safeHtml(item.platform)}}</span>
                <span class="tap-chip">${{safeHtml(item.content_format || 'other')}}</span>
                ${{item.keyword ? `<span class="tap-chip">${{safeHtml(item.keyword)}}</span>` : ''}}
              </div>
            </div>
            <span class="chip ${{scoreClass}}">${{item.recommendation_score}}</span>
          </div>
          <div class="reference-copy">${{safeHtml(preview)}}</div>
          <details class="reference-details">
            <summary>대본·번역·분석 보기</summary>
            ${{transcriptBlock}}
            ${{translationBlock}}
          </details>
          <textarea id="reference-memo-${{item.id}}" class="tap-input reference-memo" maxlength="10000" placeholder="적용 아이디어 메모">${{safeHtml(item.memo || '')}}</textarea>
          <div class="reference-actions">
            <button type="button" class="tap-btn tap-btn-ghost" onclick="patchReference('${{item.id}}', {{saved:${{!item.saved}}}})">${{item.saved ? '★ 즐겨찾기 해제' : '☆ 즐겨찾기'}}</button>
            <button type="button" class="tap-btn tap-btn-ghost" onclick="patchReference('${{item.id}}', {{read:${{!item.read}}}})">${{item.read ? '읽지 않음' : '읽음 처리'}}</button>
            <button type="button" class="tap-btn tap-btn-ghost" onclick="saveReferenceMemo('${{item.id}}')">메모 저장</button>
          </div>
        </article>
      `;
    }}).join('');
  }} catch (error) {{
    container.innerHTML = `
      <div class="reference-card">
        <div class="reference-title">레퍼런스 라이브러리를 불러오지 못했습니다.</div>
        <div class="reference-copy">로컬 저장 파일 상태를 확인해 주세요.</div>
      </div>
    `;
  }}
}}

async function createReference(event) {{
  event.preventDefault();
  const payload = {{
    title: document.getElementById('reference-title').value,
    source_url: document.getElementById('reference-url').value,
    keyword: document.getElementById('reference-keyword').value,
    platform: document.getElementById('reference-platform').value,
    recommendation_score: Number(document.getElementById('reference-score').value || 0),
    summary: document.getElementById('reference-summary').value,
  }};
  const response = await fetch('/api/reference-library', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify(payload),
  }});
  if (!response.ok) {{
    const detail = await response.json().catch(() => ({{}}));
    toast(detail.detail || '레퍼런스를 추가하지 못했습니다.');
    return;
  }}
  document.getElementById('reference-form').reset();
  document.getElementById('reference-score').value = '80';
  toast('레퍼런스를 추가했습니다.');
  await loadReferenceLibrary();
}}

async function patchReference(itemId, payload) {{
  const response = await fetch(`/api/reference-library/${{itemId}}`, {{
    method: 'PATCH',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify(payload),
  }});
  if (!response.ok) {{
    toast('레퍼런스 상태를 저장하지 못했습니다.');
    return;
  }}
  await loadReferenceLibrary();
}}

async function saveReferenceMemo(itemId) {{
  const memo = document.getElementById(`reference-memo-${{itemId}}`)?.value || '';
  await patchReference(itemId, {{ memo }});
  toast('메모를 저장했습니다.');
}}

function setTapDispatchBusy(isBusy) {{
  ['tap-dispatch-btn', 'tap-dry-run-btn', 'tap-refresh-btn'].forEach(id => {{
    const btn = document.getElementById(id);
    if (btn) btn.disabled = isBusy;
  }});
}}

function safeHtml(value) {{
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}}

async function syncTapOpsView() {{
  await Promise.all([loadTapBoard(), loadTapDealRoom(), loadTapAlerts()]);
}}

function getTapOutcomeTimestamp(item) {{
  return item.dispatched_at || item.last_attempt_at || item.queued_at || '';
}}

function renderTapOutcomes(items, scopeLabel) {{
  const container = document.getElementById('tap-outcome-list');
  if (!container) return;
  if (!items.length) {{
    container.innerHTML = `
      <div class="tap-outcome-card">
        <div class="tap-alert-title">No dispatch attempts yet${{scopeLabel}}</div>
        <div class="tap-alert-body">Dispatch and failed outcomes will appear here after the first delivery attempt.</div>
      </div>
    `;
    return;
  }}

  container.innerHTML = items.map(item => {{
    const status = String(item.lifecycle_status || '').toLowerCase();
    const cardCls = status === 'failed' ? 'tap-outcome-card tap-outcome-card-failed' : 'tap-outcome-card tap-outcome-card-success';
    const meta = item.metadata || {{}};
    const delivery = meta.last_delivery || {{}};
    const channels = ((delivery.channels || meta.channels || []))
      .map(channel => `<span class="tap-chip">${{safeHtml(channel)}}</span>`)
      .join('');
    const timestamp = safeHtml(String(getTapOutcomeTimestamp(item)).slice(0, 16).replace('T', ' ') || 'pending');
    const channelResults = Object.entries(delivery.channel_results || {{}})
      .map(([channel, result]) => {{
        const ok = !!(result && result.ok);
        const label = ok ? 'ok' : 'failed';
        const errorText = !ok && result && result.error
          ? `<div class="tap-outcome-error">${{safeHtml(result.error)}}</div>`
          : '';
        return `
          <div class="tap-outcome-detail-item">
            <strong>${{safeHtml(channel)}}</strong> · ${{label}}
            ${{errorText}}
          </div>
        `;
      }})
      .join('');
    const failureReason = delivery.failure_reason
      ? `<div class="tap-outcome-detail-item tap-outcome-error"><strong>failure</strong> · ${{safeHtml(delivery.failure_reason)}}</div>`
      : '';
    const detailBlock = channelResults || failureReason
      ? `
        <details class="tap-outcome-details">
          <summary>delivery detail</summary>
          <div class="tap-outcome-detail-list">
            ${{failureReason}}
            ${{channelResults}}
          </div>
        </details>
      `
      : '';
    return `
      <div class="${{cardCls}}">
        <div class="tap-alert-top">
          <div>
            <div class="tap-alert-title">${{safeHtml(item.keyword || 'Untitled outcome')}}</div>
            <div class="tap-alert-body">${{safeHtml(item.alert_message || 'Recent dispatch outcome')}}</div>
          </div>
          <span class="tap-chip">${{safeHtml(status || 'unknown')}}</span>
        </div>
        <div class="tap-alert-meta">
          <span class="tap-chip">priority ${{item.priority ?? '-'}}</span>
          <span class="tap-chip">score ${{item.viral_score ?? '-'}}</span>
          ${{channels}}
        </div>
        <div class="tap-outcome-time">last activity ${{timestamp}}</div>
        ${{detailBlock}}
      </div>
    `;
  }}).join('');
}}

async function loadTapAlerts() {{
  const summary = document.getElementById('tap-alert-summary');
  const list = document.getElementById('tap-alert-list');
  const status = document.getElementById('tap-alert-status');
  const targetCountry = getTapTargetCountry();
  const lifecycleStatus = getTapAlertLifecycle();
  const limit = getTapAlertLimit();
  const scopeLabel = targetCountry ? ` for ${{safeHtml(targetCountry.toUpperCase())}}` : '';
  try {{
    const countsQuery = buildTapQuery({{ limit: 50, lifecycle_status: '', target_country: targetCountry }});
    const queueQuery = buildTapQuery({{
      limit,
      lifecycle_status: lifecycleStatus,
      target_country: targetCountry,
    }});
    const dispatchedQuery = buildTapQuery({{ limit: 3, lifecycle_status: 'dispatched', target_country: targetCountry }});
    const failedQuery = buildTapQuery({{ limit: 3, lifecycle_status: 'failed', target_country: targetCountry }});
    const [countsData, queueData, dispatchedData, failedData] = await Promise.all([
      fetchDashboardJson(`/api/tap/alerts?${{countsQuery}}`, {{
        degradationKey: 'tap-alerts-counts',
        degradationLabel: 'TAP alerts',
      }}),
      fetchDashboardJson(`/api/tap/alerts?${{queueQuery}}`, {{
        degradationKey: 'tap-alerts-queue',
        degradationLabel: 'TAP alerts',
      }}),
      fetchDashboardJson(`/api/tap/alerts?${{dispatchedQuery}}`, {{
        degradationKey: 'tap-alerts-dispatched',
        degradationLabel: 'TAP alerts',
      }}),
      fetchDashboardJson(`/api/tap/alerts?${{failedQuery}}`, {{
        degradationKey: 'tap-alerts-failed',
        degradationLabel: 'TAP alerts',
      }}),
    ]);
    const counts = countsData.counts || {{}};
    const items = queueData.items || [];
    const visibleChannels = [...new Set(items.flatMap(item => ((item.metadata || {{}}).channels || [])))];
    const recentOutcomes = [...(dispatchedData.items || []), ...(failedData.items || [])]
      .sort((a, b) => String(getTapOutcomeTimestamp(b)).localeCompare(String(getTapOutcomeTimestamp(a))))
      .slice(0, 4);

    summary.innerHTML = `
      <div class="tap-summary-card"><div class="tap-summary-label">Queued</div><div class="tap-summary-value">${{counts.queued || 0}}</div></div>
      <div class="tap-summary-card"><div class="tap-summary-label">Dispatched</div><div class="tap-summary-value">${{counts.dispatched || 0}}</div></div>
      <div class="tap-summary-card"><div class="tap-summary-label">Failed</div><div class="tap-summary-value">${{counts.failed || 0}}</div></div>
      <div class="tap-summary-card"><div class="tap-summary-label">Channels</div><div class="tap-summary-value">${{visibleChannels.length}}</div></div>
    `;
    renderTapOutcomes(recentOutcomes, scopeLabel);

    if (!items.length) {{
      const stateLabel = lifecycleStatus || 'all';
      list.innerHTML = `
        <div class="tap-alert-item">
          <div class="tap-alert-title">No ${{safeHtml(stateLabel)}} alerts${{scopeLabel}}</div>
          <div class="tap-alert-body">Fresh TAP signals will appear here once the queue is refilled or the selected lifecycle changes.</div>
        </div>
      `;
      status.textContent = `Queue view is empty${{scopeLabel}}.`;
      return;
    }}

    list.innerHTML = items.map(item => {{
      const meta = item.metadata || {{}};
      const route = [item.source_country, item.target_country]
        .filter(Boolean)
        .map(country => safeHtml(String(country).toUpperCase()))
        .join(' -> ');
      const chips = [
        `priority ${{item.priority ?? '-'}}`,
        `score ${{item.viral_score ?? '-'}}`,
        item.paywall_tier || 'premium',
      ].map(value => `<span class="tap-chip">${{safeHtml(value)}}</span>`).join('');
      const channels = (meta.channels || [])
        .map(channel => `<span class="tap-chip">${{safeHtml(channel)}}</span>`)
        .join('');
      const queuedAt = item.queued_at
        ? safeHtml(String(item.queued_at).slice(0, 16).replace('T', ' '))
        : 'pending';

      return `
        <div class="tap-alert-item">
          <div class="tap-alert-top">
            <div>
              <div class="tap-alert-title">${{safeHtml(item.keyword || 'Untitled alert')}}</div>
              <div class="tap-alert-body">${{safeHtml(item.alert_message || 'Queued TAP alert')}}</div>
            </div>
            <span class="tap-chip">${{safeHtml(item.lifecycle_status || 'queued')}}</span>
          </div>
          <div class="tap-alert-meta">${{chips}}${{channels}}</div>
          <div class="tap-lock">${{route || 'Route pending'}} | queued ${{queuedAt}}</div>
        </div>
      `;
    }}).join('');
    const stateLabel = lifecycleStatus || 'all';
    status.textContent = `${{items.length}} ${{stateLabel}} alert(s) loaded${{scopeLabel}}.`;
  }} catch(e) {{
    summary.innerHTML = `
      <div class="tap-summary-card"><div class="tap-summary-label">Queued</div><div class="tap-summary-value">-</div></div>
      <div class="tap-summary-card"><div class="tap-summary-label">Dispatched</div><div class="tap-summary-value">-</div></div>
      <div class="tap-summary-card"><div class="tap-summary-label">Failed</div><div class="tap-summary-value">-</div></div>
      <div class="tap-summary-card"><div class="tap-summary-label">Channels</div><div class="tap-summary-value">-</div></div>
    `;
    list.innerHTML = `
      <div class="tap-alert-item">
        <div class="tap-alert-title">Queue unavailable</div>
        <div class="tap-alert-body">The dashboard could not load queued TAP alerts.</div>
      </div>
    `;
    renderTapOutcomes([], scopeLabel);
    status.textContent = `Unable to load TAP alert queue${{scopeLabel}}.`;
  }}
}}

async function dispatchTapAlerts(dryRun = false) {{
  const status = document.getElementById('tap-alert-status');
  const targetCountry = getTapTargetCountry();
  const limit = getTapAlertLimit();
  const scopeLabel = targetCountry ? ` for ${{targetCountry.toUpperCase()}}` : '';
  setTapDispatchBusy(true);
  status.textContent = dryRun ? `Running dry run${{scopeLabel}}...` : `Dispatching queued alerts${{scopeLabel}}...`;
  try {{
    const query = buildTapQuery({{
      limit,
      dry_run: dryRun ? 'true' : 'false',
      target_country: targetCountry,
    }});
    const resp = await fetch(`/api/tap/alerts/dispatch?${{query}}`, {{ method: 'POST' }});
    if (!resp.ok) throw new Error('tap_alert_dispatch_failed');
    const data = await resp.json();
    const message = dryRun
      ? `Dry run checked ${{(data.items || []).length}} alert(s) across ${{(data.channels || []).length}} channel(s)${{scopeLabel}}.`
      : `Dispatch finished${{scopeLabel}}: ${{data.dispatched || 0}} sent, ${{data.failed || 0}} failed, ${{data.skipped || 0}} skipped.`;
    status.textContent = message;
    toast(message);
    await syncTapOpsView();
  }} catch(e) {{
    const message = dryRun ? `Dry run failed${{scopeLabel}}.` : `Dispatch failed${{scopeLabel}}.`;
    status.textContent = message;
    toast(message);
  }} finally {{
    setTapDispatchBusy(false);
  }}
}}

async function init() {{
  renderTapPresetStrip();
  handleTapCheckoutStateFromUrl();
  await Promise.all([loadStats(), loadPipeline(), loadTimeline(), loadCategories(), loadSourceQuality(), loadLogs(), loadAbTest(), loadTapBoard(), loadTapDealRoom(), loadTapAlerts(), loadReferenceLibrary()]);
  await Promise.all([refreshFastViral(true), refreshXRadar(true), refreshLiveReferences(true)]);
  toast('✅ 대시보드 로드 완료');
}}
init();

// Auto-refresh: pipeline status & logs 30s, full data 5min
setInterval(() => {{ loadPipeline(); loadLogs(); }}, 30000);
setInterval(async () => {{
  await Promise.all([loadStats(), loadTimeline(), loadCategories(), loadSourceQuality(), loadTapBoard(), loadTapDealRoom(), loadTapAlerts(), loadReferenceLibrary()]);
  toast('🔄 데이터 갱신 완료');
}}, 300000);
setInterval(() => refreshLiveReferences(true), 600000);
setInterval(() => refreshXRadar(true), 120000);
setInterval(() => refreshFastViral(true), 120000);
</script>
</body>
</html>"""
