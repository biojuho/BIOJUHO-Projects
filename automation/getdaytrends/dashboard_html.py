"""Clean HTML template for the getdaytrends operator dashboard."""

from __future__ import annotations


def get_dashboard_html(version: str) -> str:
    """Return the full dashboard HTML with the runtime version inserted."""

    return _HTML_TEMPLATE.replace("__VERSION__", version)


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>getdaytrends Pro Dashboard v__VERSION__</title>
<link rel="icon" href="data:,">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: Inter, system-ui, sans-serif; background: #0a0f1f; color: #e5edf7; min-height: 100vh; }
  header { display: flex; align-items: center; gap: 14px; padding: 16px 28px; background: #101827; border-bottom: 1px solid rgba(148,163,184,.18); position: sticky; top: 0; z-index: 10; }
  header h1 { font-size: 1.18rem; font-weight: 800; letter-spacing: 0; }
  .badge { border: 1px solid rgba(56,189,248,.32); color: #67e8f9; border-radius: 6px; padding: 3px 9px; font-size: .72rem; font-weight: 700; }
  .status-pill { margin-left: auto; border-radius: 999px; padding: 7px 13px; font-size: .78rem; font-weight: 700; border: 1px solid transparent; }
  .st-idle { background: rgba(34,197,94,.13); color: #4ade80; border-color: rgba(34,197,94,.26); }
  .st-running { background: rgba(245,158,11,.14); color: #fbbf24; border-color: rgba(245,158,11,.3); }
  .st-error { background: rgba(239,68,68,.14); color: #f87171; border-color: rgba(239,68,68,.3); }
  .dashboard-warning-banner { display: none; margin: 14px 28px 0; padding: 13px 15px; border-radius: 8px; border: 1px solid rgba(245,158,11,.34); background: rgba(120,53,15,.32); color: #fde68a; gap: 9px; }
  .dashboard-warning-banner.show { display: grid; }
  .dashboard-warning-status { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
  .dashboard-warning-actions { display: flex; align-items: center; justify-content: flex-end; flex-wrap: wrap; gap: 8px; margin-left: auto; }
  .dashboard-warning-chip { display: inline-flex; align-items: center; border-radius: 999px; padding: 3px 8px; margin-left: 6px; background: rgba(251,191,36,.15); color: #fcd34d; font-size: .72rem; font-weight: 700; }
  .dashboard-warning-details { border-top: 1px solid rgba(251,191,36,.2); padding-top: 7px; color: #fde68a; }
  .dashboard-warning-details summary { cursor: pointer; min-height: 28px; padding: 6px 0; font-size: .74rem; font-weight: 800; line-height: 1.35; }
  .dashboard-warning-list { display: grid; gap: 5px; margin-top: 7px; list-style: none; }
  .dashboard-warning-list li { display: grid; gap: 3px; padding: 7px 8px; border-radius: 6px; background: rgba(15,23,42,.46); overflow-wrap: anywhere; }
  .dashboard-warning-list code { color: #fef3c7; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: .68rem; }
  .dashboard-warning-meta { color: #fbbf24; font-size: .68rem; }
  .dashboard-warning-recovery { display: grid; gap: 5px; padding: 8px; border-radius: 6px; background: rgba(15,23,42,.36); font-size: .74rem; line-height: 1.45; overflow-wrap: anywhere; }
  .dashboard-warning-recovery code { color: #fef3c7; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: .68rem; }
  .tap-checkout-return-notice { margin: 14px 28px 0; padding: 13px 15px; border-radius: 8px; display: flex; align-items: center; justify-content: space-between; gap: 12px; border: 1px solid rgba(56,189,248,.3); background: #0b2338; color: #e0f2fe; }
  .tap-checkout-return-notice[hidden] { display: none; }
  .tap-checkout-return-success { border-color: rgba(34,197,94,.34); background: rgba(20,83,45,.32); color: #dcfce7; }
  .tap-checkout-return-cancel { border-color: rgba(245,158,11,.34); background: rgba(120,53,15,.32); color: #fde68a; }
  .tap-checkout-return-meta { color: inherit; opacity: .82; font-size: .74rem; line-height: 1.45; margin-top: 4px; overflow-wrap: anywhere; }
  .tap-checkout-return-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
  .tap-checkout-session-status { color: inherit; opacity: .9; font-size: .74rem; line-height: 1.45; margin-top: 4px; overflow-wrap: anywhere; }
  .kpi-grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; padding: 20px 28px; }
  .kpi, .panel { background: #121b2c; border: 1px solid rgba(148,163,184,.14); border-radius: 8px; }
  .kpi { min-height: 116px; padding: 16px; }
  .label { color: #8ea3bb; font-size: .68rem; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }
  .value { margin-top: 7px; color: #f8fafc; font-size: 1.65rem; font-weight: 800; line-height: 1.05; }
  .sub { color: #64748b; font-size: .72rem; margin-top: 6px; }
  .budget-track { margin-top: 8px; height: 6px; background: #233047; border-radius: 999px; overflow: hidden; }
  .budget-fill { height: 100%; width: 0; border-radius: 999px; background: linear-gradient(90deg,#38bdf8,#22c55e); transition: width .35s ease; }
  .budget-fill.warn { background: linear-gradient(90deg,#f59e0b,#ef4444); }
  .layout-main { display: grid; grid-template-columns: 2fr 1fr; gap: 14px; padding: 0 28px 14px; }
  .layout-three { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; padding: 0 28px 14px; }
  .layout-main > *, .layout-three > *, .kpi-grid > *, .tap-grid > *, .tap-deal-grid > *, .operator-grid > * { min-width: 0; }
  .panel { padding: 18px; min-height: 250px; min-width: 0; }
  .panel h3 { color: #b6c5d8; font-size: .8rem; font-weight: 800; letter-spacing: .04em; text-transform: uppercase; margin-bottom: 14px; }
  canvas { display: block; width: 100% !important; max-width: 100%; max-height: 280px; }
  .tap-grid, .tap-deal-grid, .tap-alert-list, .tap-outcome-list { display: grid; gap: 10px; }
  .tap-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .tap-deal-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .tap-card, .tap-deal-card, .tap-alert-item, .tap-outcome-card, .tap-summary-card { background: #0f172a; border: 1px solid rgba(148,163,184,.13); border-radius: 8px; padding: 12px; }
  .tap-title, .tap-alert-title { color: #f8fafc; font-size: .9rem; font-weight: 800; line-height: 1.3; }
  .tap-copy, .tap-alert-body { color: #c5d3e3; font-size: .8rem; line-height: 1.5; margin-top: 7px; }
  .tap-notes, .tap-lock, .tap-status, .tap-outcome-time { color: #7d91aa; font-size: .74rem; line-height: 1.45; margin-top: 8px; }
  .tap-meta, .tap-actions, .tap-preset-strip { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-top: 10px; }
  .tap-chip { display: inline-flex; align-items: center; border-radius: 999px; padding: 3px 8px; background: rgba(56,189,248,.11); color: #7dd3fc; font-size: .72rem; font-weight: 700; }
  .tap-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin-bottom: 12px; }
  .tap-summary-label { color: #7d91aa; font-size: .66rem; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; }
  .tap-summary-value { color: #f8fafc; margin-top: 5px; font-size: 1.06rem; font-weight: 800; }
  .tap-deal-card-wide { grid-column: 1 / -1; }
  .tap-deal-ops-grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 8px; margin-top: 10px; }
  .tap-deal-metric { border: 1px solid rgba(148,163,184,.12); border-radius: 8px; background: #0b1220; padding: 9px; min-width: 0; }
  .tap-deal-metric-label { color: #7d91aa; font-size: .62rem; font-weight: 800; text-transform: uppercase; letter-spacing: .04em; }
  .tap-deal-metric-value { color: #f8fafc; margin-top: 5px; font-size: 1rem; font-weight: 900; overflow-wrap: anywhere; }
  .tap-control-row { display: grid; grid-template-columns: 1.4fr 1fr 1fr; gap: 10px; margin-bottom: 10px; }
  .tap-control { display: flex; flex-direction: column; gap: 5px; color: #8ea3bb; font-size: .68rem; font-weight: 800; text-transform: uppercase; letter-spacing: .04em; }
  .tap-input { width: 100%; border-radius: 8px; border: 1px solid rgba(148,163,184,.2); background: #0b1220; color: #e5edf7; padding: 9px 10px; outline: none; }
  .tap-input:focus { border-color: rgba(56,189,248,.52); box-shadow: 0 0 0 2px rgba(56,189,248,.12); }
  .tap-btn, .tap-preset-btn { appearance: none; border: 0; border-radius: 8px; cursor: pointer; font-weight: 800; transition: transform .15s ease, opacity .15s ease; }
  .tap-btn { padding: 9px 12px; background: #fbbf24; color: #111827; font-size: .78rem; }
  .tap-btn-ghost, .tap-preset-btn { border: 1px solid rgba(148,163,184,.2); background: #0b1220; color: #cbd5e1; }
  .tap-preset-btn { padding: 6px 9px; font-size: .72rem; border-radius: 999px; }
  .tap-preset-btn-active { border-color: rgba(56,189,248,.56); color: #e0f2fe; background: rgba(56,189,248,.12); }
  .tap-btn:hover, .tap-preset-btn:hover { transform: translateY(-1px); }
  .tap-btn:disabled { cursor: wait; opacity: .55; transform: none; }
  .tap-badge { display: inline-flex; border-radius: 999px; padding: 3px 7px; background: rgba(34,197,94,.13); color: #4ade80; font-size: .68rem; font-weight: 800; }
  .tap-price { color: #fbbf24; font-weight: 900; }
  .operator-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
  .operator-card, .operator-item { background: #0f172a; border: 1px solid rgba(148,163,184,.13); border-radius: 8px; padding: 12px; }
  .operator-value { color: #f8fafc; font-size: 1.25rem; font-weight: 900; line-height: 1.1; margin-top: 6px; }
  .operator-card-detail { color: #9fb1c7; font-size: .72rem; line-height: 1.38; margin-top: 7px; overflow-wrap: anywhere; }
  .operator-state { display: inline-flex; margin-top: 9px; border-radius: 999px; padding: 3px 8px; font-size: .68rem; font-weight: 800; }
  .operator-pass { background: rgba(34,197,94,.13); color: #4ade80; }
  .operator-warn { background: rgba(245,158,11,.14); color: #fbbf24; }
  .operator-fail { background: rgba(239,68,68,.14); color: #f87171; }
  .operator-unknown { background: rgba(148,163,184,.12); color: #cbd5e1; }
  .operator-list { display: grid; gap: 9px; }
  .operator-item-title { color: #f8fafc; font-size: .82rem; font-weight: 850; }
  .operator-item-body { color: #9fb1c7; font-size: .78rem; line-height: 1.45; margin-top: 5px; }
  .operator-action { margin-top: 8px; color: #cbd5e1; font-size: .72rem; line-height: 1.45; }
  .operator-action-head { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; margin-bottom: 4px; }
  .operator-action-title, .operator-action-button-group { display: inline-flex; align-items: center; flex-wrap: wrap; gap: 4px; min-width: 0; }
  .operator-action-title { flex: 1 1 260px; }
  .operator-action-button-group { flex: 0 0 auto; justify-content: flex-end; margin-left: auto; }
  .operator-action-label { color: #cbd5e1; font-weight: 800; min-width: 0; overflow-wrap: anywhere; }
  .operator-action-note { border: 1px solid rgba(148,163,184,.16); border-radius: 6px; background: #111c2f; color: #9fb1c7; font-size: .66rem; font-weight: 800; line-height: 1.2; padding: 2px 6px; overflow-wrap: anywhere; }
  .operator-action-note-fresh { border-color: rgba(34,197,94,.34); background: rgba(34,197,94,.1); color: #86efac; }
  .operator-action-note-stale { border-color: rgba(245,158,11,.38); background: rgba(245,158,11,.1); color: #fbbf24; }
  .operator-copy-btn { border: 1px solid rgba(148,163,184,.22); background: #111c2f; color: #e2e8f0; border-radius: 6px; cursor: pointer; font-size: .68rem; font-weight: 800; line-height: 1.2; min-height: 28px; min-width: 56px; padding: 4px 8px; }
  .operator-copy-btn-primary { background: #0b3b52; border-color: rgba(125,211,252,.62); color: #f0f9ff; box-shadow: inset 0 0 0 1px rgba(125,211,252,.18); }
  .operator-copy-btn:hover { background: #172235; border-color: rgba(56,189,248,.5); color: #f8fafc; }
  .operator-copy-btn-primary:hover { background: #0d4a64; border-color: rgba(125,211,252,.82); color: #f8fafc; }
  .operator-copy-btn:focus-visible { outline: 2px solid #38bdf8; outline-offset: 2px; }
  .operator-view-btn { border: 1px solid rgba(56,189,248,.25); background: #0b2338; color: #e0f2fe; border-radius: 6px; cursor: pointer; font-size: .68rem; font-weight: 800; line-height: 1.2; min-height: 28px; min-width: 52px; padding: 4px 8px; }
  .operator-view-btn:hover { background: #12314d; border-color: rgba(56,189,248,.55); color: #f0f9ff; }
  .operator-view-btn:focus-visible { outline: 2px solid #38bdf8; outline-offset: 2px; }
  .operator-action code { display: block; padding: 7px 8px; border-radius: 6px; background: #0b1220; color: #f8fafc; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; white-space: normal; overflow-wrap: anywhere; }
  .operator-packet-preview { margin-top: 6px; display: grid; gap: 4px; color: #cbd5e1; font-size: .72rem; line-height: 1.45; }
  .operator-packet-preview span { display: block; padding: 5px 7px; border: 1px solid rgba(148,163,184,.12); border-radius: 6px; background: #0b1220; overflow-wrap: anywhere; }
  .operator-packet-preview .operator-packet-action-group { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
  .operator-packet-preview code, .operator-packet-preview samp { display: block; margin-top: 3px; color: #e2e8f0; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: .68rem; white-space: pre-wrap; overflow-wrap: anywhere; }
  .operator-reference-link { display: inline-flex; margin-left: 6px; color: #7dd3fc; font-weight: 850; text-decoration: none; border-bottom: 1px solid rgba(125,211,252,.4); }
  .operator-reference-link:hover { color: #e0f2fe; border-bottom-color: rgba(224,242,254,.85); }
  .operator-artifact-image-preview { display: block; width: 100%; max-height: 360px; border: 1px solid rgba(148,163,184,.18); border-radius: 6px; background: #020617; object-fit: contain; }
  .operator-diagnostics { margin-top: 8px; display: grid; gap: 4px; }
  .operator-diagnostics code { display: block; padding: 6px 8px; border-radius: 6px; background: #0b1220; color: #dbeafe; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: .68rem; white-space: normal; overflow-wrap: anywhere; }
  .operator-evidence-summary { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 6px; }
  .operator-evidence-summary span { display: inline-flex; align-items: center; min-height: 24px; padding: 3px 8px; border-radius: 999px; background: #fff7ed; color: #9a3412; border: 1px solid #fed7aa; font-size: .72rem; font-weight: 700; }
  .table-wrap { padding: 0 28px 28px; overflow-x: auto; }
  table { width: 100%; min-width: 760px; border-collapse: collapse; background: #121b2c; border: 1px solid rgba(148,163,184,.14); border-radius: 8px; overflow: hidden; }
  .visually-hidden { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
  .skip-link { position: fixed; left: 16px; top: 12px; z-index: 30; transform: translateY(-160%); border: 1px solid rgba(56,189,248,.45); border-radius: 6px; background: #0b2338; color: #e0f2fe; padding: 8px 10px; font-size: .78rem; font-weight: 800; text-decoration: none; }
  .skip-link:focus-visible { transform: translateY(0); outline: 2px solid #38bdf8; outline-offset: 2px; }
  th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid rgba(148,163,184,.08); font-size: .8rem; }
  th { color: #8ea3bb; background: #172235; font-size: .68rem; font-weight: 800; text-transform: uppercase; letter-spacing: .04em; }
  .score-high { color: #4ade80; }
  .score-mid { color: #fbbf24; }
  .score-low { color: #f87171; }
  .log-viewer { background: #0b1220; border-radius: 8px; min-height: 225px; max-height: 225px; overflow-y: auto; padding: 12px; color: #a5b4fc; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: .74rem; line-height: 1.45; overflow-wrap: anywhere; word-break: break-word; }
  .log-viewer > div { min-width: 0; overflow-wrap: anywhere; word-break: break-word; }
  .manual-copy { position: fixed; right: 22px; bottom: 72px; width: min(460px, calc(100vw - 44px)); display: none; gap: 8px; z-index: 19; border: 1px solid rgba(248,113,113,.45); border-radius: 8px; background: #111827; box-shadow: 0 18px 42px rgba(0,0,0,.42); padding: 12px; }
  .manual-copy.show { display: grid; }
  .manual-copy-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; color: #fee2e2; font-size: .78rem; font-weight: 900; }
  .manual-copy-close { border: 1px solid rgba(248,113,113,.35); background: #1f2937; color: #fee2e2; border-radius: 6px; cursor: pointer; font-size: .68rem; font-weight: 800; padding: 4px 8px; }
  .manual-copy-close:focus-visible { outline: 2px solid #f87171; outline-offset: 2px; }
  .manual-copy textarea { width: 100%; min-height: 112px; resize: vertical; border: 1px solid rgba(148,163,184,.24); border-radius: 6px; background: #020617; color: #f8fafc; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: .72rem; line-height: 1.45; padding: 8px; }
  .toast { position: fixed; bottom: 22px; right: 22px; transform: translateY(80px); opacity: 0; transition: all .25s ease; background: #16a34a; color: white; border-radius: 8px; padding: 10px 14px; font-size: .82rem; font-weight: 800; z-index: 20; }
  .toast.error { background: #dc2626; }
  .toast.show { transform: translateY(0); opacity: 1; }
  .footer { color: #64748b; font-size: .72rem; text-align: center; padding: 18px; }
  @media (max-width: 1200px) { .kpi-grid { grid-template-columns: repeat(3,1fr); } .layout-main, .layout-three, .tap-grid, .tap-deal-grid { grid-template-columns: 1fr; } .operator-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .tap-deal-ops-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
  @media (max-width: 760px) { header, .kpi-grid, .layout-main, .layout-three, .table-wrap { padding-left: 14px; padding-right: 14px; } .kpi-grid, .tap-summary, .tap-control-row, .tap-deal-ops-grid { grid-template-columns: 1fr; } }
  @media (max-width: 560px) { .operator-grid { grid-template-columns: 1fr; } .operator-action-head { align-items: flex-start; flex-direction: column; } .operator-action-title, .operator-action-button-group { justify-content: flex-start; } .operator-action-title { flex: 0 1 auto; } .operator-action-button-group { margin-left: 0; } .manual-copy { left: 14px; right: 14px; bottom: 78px; width: auto; } }
</style>
</head>
<body>
<a class="skip-link" href="#dashboard-main">Skip to dashboard content</a>
<header>
  <h1>getdaytrends Pro</h1>
  <span class="badge">v__VERSION__</span>
  <div id="status-pill" class="status-pill st-idle" role="status" aria-live="polite" aria-atomic="true" aria-label="Dashboard status">Loading</div>
</header>
<main id="dashboard-main" tabindex="-1">
<div id="dashboard-warning-banner" class="dashboard-warning-banner"></div>
<div id="tap-checkout-return-notice" class="tap-checkout-return-notice" role="status" aria-live="polite" aria-atomic="true" hidden></div>

<section class="kpi-grid" id="kpi-grid">
  <div class="kpi"><div class="label">Total runs</div><div class="value" id="k-runs">-</div></div>
  <div class="kpi"><div class="label">Total trends</div><div class="value" id="k-trends">-</div></div>
  <div class="kpi"><div class="label">Avg viral score</div><div class="value" id="k-score">-</div><div class="sub">/ 100</div></div>
  <div class="kpi"><div class="label">Generated posts</div><div class="value" id="k-tweets">-</div></div>
  <div class="kpi"><div class="label">7d LLM cost</div><div class="value" id="k-cost">$0.0000</div><div class="sub" id="k-cost-sub">Monthly estimate $0.00</div></div>
  <div class="kpi"><div class="label">Budget today</div><div class="value" id="k-budget">-</div><div class="sub" id="k-budget-sub"></div><div class="budget-track"><div class="budget-fill" id="k-budget-bar"></div></div></div>
</section>

<section class="layout-main">
  <div class="panel"><h3>Viral score timeline</h3><canvas id="chart-timeline" role="img" aria-label="Viral score timeline chart showing recent trend viral scores from zero to 100.">Viral score timeline chart showing recent trend viral scores from zero to 100.</canvas></div>
  <div class="panel"><h3>Category mix</h3><canvas id="chart-category" role="img" aria-label="Category mix chart showing trend category counts.">Category mix chart showing trend category counts.</canvas></div>
</section>
<section class="layout-three">
  <div class="panel"><h3>Source quality</h3><canvas id="chart-source" role="img" aria-label="Source quality radar chart comparing source success rate and quality score.">Source quality radar chart comparing source success rate and quality score.</canvas></div>
  <div class="panel"><h3>Daily LLM cost</h3><canvas id="chart-cost" role="img" aria-label="Daily LLM cost chart showing daily spend in USD.">Daily LLM cost chart showing daily spend in USD.</canvas></div>
  <div class="panel"><h3>Trend acceleration top 10</h3><canvas id="chart-accel" role="img" aria-label="Trend acceleration top 10 chart ranking the fastest moving trend acceleration values.">Trend acceleration top 10 chart ranking the fastest moving trend acceleration values.</canvas></div>
</section>
<section class="layout-main">
  <div class="panel"><h3>A/B test result</h3><div id="ab-test-content" class="tap-grid"></div></div>
  <div class="panel"><h3>Pipeline logs</h3><div id="log-viewer" class="log-viewer" role="log" aria-live="polite" aria-atomic="false" aria-relevant="additions text" aria-label="Pipeline logs"><div>Loading logs...</div></div></div>
</section>
<section class="layout-main">
  <div class="panel"><h3>Operator readiness</h3><div id="operator-readiness" class="operator-grid"></div><div id="operator-artifacts" class="operator-list"></div></div>
  <div class="panel"><h3>Posting blockers</h3><div id="operator-blockers" class="operator-list"></div></div>
</section>
<section class="layout-main">
  <div class="panel"><h3>TAP Pro: cross-country first-mover radar</h3><div id="tap-board" class="tap-grid"></div></div>
  <div class="panel">
    <h3>TAP alert queue ops</h3>
    <div id="tap-alert-summary" class="tap-summary"></div>
    <div class="tap-control-row" role="group" aria-label="TAP alert queue filters" data-tap-alert-filters="true">
      <div class="tap-control"><label id="tap-target-country-label" for="tap-target-country">Target market</label><input id="tap-target-country" class="tap-input" placeholder="all markets" aria-labelledby="tap-target-country-label" onchange="syncTapOpsView()" onkeydown="handleTapTargetMarketKey(event)"></div>
      <div class="tap-control"><label id="tap-alert-lifecycle-label" for="tap-alert-lifecycle">Lifecycle</label><select id="tap-alert-lifecycle" class="tap-input" aria-labelledby="tap-alert-lifecycle-label" onchange="loadTapAlerts()"><option value="queued">Queued</option><option value="">All states</option><option value="dispatched">Dispatched</option><option value="failed">Failed</option></select></div>
      <div class="tap-control"><label id="tap-alert-limit-label" for="tap-alert-limit">Batch size</label><select id="tap-alert-limit" class="tap-input" aria-labelledby="tap-alert-limit-label" onchange="loadTapAlerts()"><option value="5">5</option><option value="6" selected>6</option><option value="10">10</option><option value="20">20</option></select></div>
    </div>
    <div class="tap-preset-strip" role="group" aria-label="TAP target market preset actions" data-tap-preset-actions="true"><div id="tap-preset-strip" class="tap-preset-strip" role="group" aria-label="TAP target market presets" data-tap-preset-options="true"></div><button type="button" id="tap-save-preset-btn" class="tap-btn tap-btn-ghost" aria-label="Save TAP target market preset" onclick="saveCurrentTapPreset()">Save preset</button><button type="button" id="tap-clear-presets-btn" class="tap-btn tap-btn-ghost" aria-label="Reset TAP target market presets" onclick="resetTapPresets()">Reset presets</button></div>
    <div class="tap-actions" role="group" aria-label="TAP alert queue actions" data-tap-alert-actions="true"><button type="button" id="tap-dispatch-btn" class="tap-btn" aria-label="Dispatch queued TAP alerts" onclick="dispatchTapAlerts(false)">Dispatch queued</button><button type="button" id="tap-dry-run-btn" class="tap-btn tap-btn-ghost" aria-label="Dry run TAP alert dispatch" onclick="dispatchTapAlerts(true)">Dry run</button><button type="button" id="tap-refresh-btn" class="tap-btn tap-btn-ghost" aria-label="Refresh TAP alert queue" onclick="syncTapOpsView()">Refresh queue</button></div>
    <div id="tap-alert-status" class="tap-status" role="status" aria-live="polite" aria-atomic="true" aria-busy="false">Queue status will appear here.</div>
    <div id="tap-alert-list" class="tap-alert-list"></div>
    <div class="tap-lock">Recent dispatch outcomes</div>
    <div id="tap-outcome-list" class="tap-outcome-list"></div>
  </div>
</section>
<section class="layout-main">
  <div class="panel"><h3>TAP deal room: teaser to premium conversion</h3><div id="tap-deal-room" class="tap-deal-grid"></div></div>
</section>
<section class="table-wrap">
  <table>
    <caption class="visually-hidden">Latest scored trends</caption>
    <thead><tr><th scope="col">#</th><th scope="col">Keyword</th><th scope="col">Viral</th><th scope="col">Country</th><th scope="col">Acceleration</th><th scope="col">Insight</th><th scope="col">Scored at</th></tr></thead>
    <tbody id="t-body"></tbody>
  </table>
</section>
</main>
<footer class="footer">getdaytrends Pro Dashboard - Auto-refresh 30s - Built with FastAPI + Chart.js</footer>
<div class="manual-copy" id="manual-copy-panel" role="dialog" aria-modal="false" aria-labelledby="manual-copy-title" hidden>
  <div class="manual-copy-head">
    <strong id="manual-copy-title">Manual copy</strong>
    <button type="button" class="manual-copy-close" onclick="hideManualCopy()" aria-label="Close manual copy panel">Close</button>
  </div>
  <textarea id="manual-copy-text" readonly spellcheck="false" aria-label="Manual copy text"></textarea>
</div>
<div class="toast" id="toast" role="status" aria-live="polite" aria-atomic="true"></div>

<script>
const C = { indigo: '#6366f1', sky: '#38bdf8', green: '#22c55e', amber: '#f59e0b', red: '#ef4444', pink: '#ec4899', slate: '#64748b', grid: 'rgba(148,163,184,.09)' };
const PALETTE = [C.sky, C.green, C.amber, C.pink, C.indigo, C.red, C.slate];
const ChartRuntime = window.Chart || class { constructor() {} destroy() {} };
ChartRuntime.defaults = ChartRuntime.defaults || {};
ChartRuntime.defaults.color = '#94a3b8';
ChartRuntime.defaults.font = ChartRuntime.defaults.font || {};
ChartRuntime.defaults.font.family = 'Inter';
ChartRuntime.defaults.plugins = ChartRuntime.defaults.plugins || {};
ChartRuntime.defaults.plugins.legend = ChartRuntime.defaults.plugins.legend || {};
ChartRuntime.defaults.plugins.legend.labels = ChartRuntime.defaults.plugins.legend.labels || {};
ChartRuntime.defaults.plugins.legend.labels.boxWidth = 10;

const charts = {};
const degradations = new Map();
const FALLBACK_RECOVERY_PACKET_PATH = 'logs\\\\readiness\\\\supabase_recovery_packet_latest.json';
const FALLBACK_READINESS_REFRESH_COMMAND = 'python scripts\\\\readiness_check.py --max-scheduler-age-hours 24 --max-cli-smoke-age-hours 24 --max-browser-smoke-age-hours 24 --fail-on-runtime-fallback --require-live-db';
const TAP_PRESET_STORAGE_KEY = 'getdaytrends.tap-target-presets';
const OPERATOR_COPY_RESET_DELAY_MS = 1500;
const operatorCopyResetTimers = new WeakMap();
let currentTapDealRoomOffers = [];
let manualCopyFocusTarget = null;

function safeHtml(value) {
  return String(value ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function operatorDisplayCheckName(item) {
  if (!item || typeof item !== 'object') return 'unknown';
  const rawName = String(item.name || 'unknown').trim() || 'unknown';
  const displayName = String(item.display_name || '').trim();
  return displayName && displayName !== rawName ? `${displayName} (${rawName})` : rawName;
}

function safeExternalHref(value) {
  try {
    const url = new URL(String(value || '').trim());
    return url.protocol === 'https:' ? url.href : '';
  } catch {
    return '';
  }
}

function renderOperatorReferenceLinks(referenceLinks) {
  const links = (Array.isArray(referenceLinks) ? referenceLinks : [])
    .map(item => {
      const label = String(item?.label || '').trim();
      const href = safeExternalHref(item?.url || '');
      return label && href ? { label, href } : null;
    })
    .filter(Boolean)
    .slice(0, 5);
  if (!links.length) return '';
  return `<span class="operator-reference-list">References: ${links.map(link => `<a class="operator-reference-link" href="${safeHtml(link.href)}" target="_blank" rel="noopener noreferrer">${safeHtml(link.label)}</a>`).join(' ')}</span>`;
}

function safeId(value, fallback = 'panel') {
  const normalized = String(value || fallback).toLowerCase().replace(/[^a-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 72);
  return normalized || fallback;
}

function setOperatorDisclosureState(button, preview, expanded) {
  if (preview) preview.hidden = !expanded;
  if (!button) return;
  const viewLabel = button.dataset.viewLabel || button.getAttribute('aria-label') || 'View preview';
  const hideLabel = button.dataset.hideLabel || viewLabel.replace(/^View\\b/, 'Hide');
  const viewText = button.dataset.viewText || viewLabel;
  const hideText = button.dataset.hideText || hideLabel;
  button.dataset.viewLabel = viewLabel;
  button.dataset.hideLabel = hideLabel;
  button.dataset.viewText = viewText;
  button.dataset.hideText = hideText;
  button.setAttribute('aria-expanded', expanded ? 'true' : 'false');
  button.setAttribute('aria-label', expanded ? hideLabel : viewLabel);
  button.innerText = expanded ? hideText : viewText;
}

function setOperatorPreviewBusy(button, preview, isBusy) {
  if (button) button.setAttribute('aria-busy', isBusy ? 'true' : 'false');
  if (preview) preview.setAttribute('aria-busy', isBusy ? 'true' : 'false');
}

function collapseOperatorPreview(button, preview) {
  if (button?.getAttribute('aria-expanded') !== 'true' || !preview || preview.hidden) return false;
  preview.innerHTML = '';
  setOperatorPreviewBusy(button, preview, false);
  setOperatorDisclosureState(button, preview, false);
  return true;
}

function toast(message, type = 'success') {
  const el = document.getElementById('toast');
  const isError = type === 'error';
  el.textContent = message;
  el.setAttribute('role', isError ? 'alert' : 'status');
  el.setAttribute('aria-live', isError ? 'assertive' : 'polite');
  el.dataset.lastToastType = isError ? 'error' : 'success';
  el.dataset.lastToastRole = isError ? 'alert' : 'status';
  el.dataset.lastToastLive = isError ? 'assertive' : 'polite';
  el.classList.toggle('error', isError);
  el.classList.add('show');
  setTimeout(() => {
    el.classList.remove('show');
    el.classList.remove('error');
    el.setAttribute('role', 'status');
    el.setAttribute('aria-live', 'polite');
  }, 2600);
}

function hideManualCopy(options = {}) {
  const restoreFocus = options.restoreFocus !== false;
  const focusTarget = manualCopyFocusTarget;
  manualCopyFocusTarget = null;
  const panel = document.getElementById('manual-copy-panel');
  const textarea = document.getElementById('manual-copy-text');
  if (panel) {
    panel.classList.remove('show');
    panel.hidden = true;
    panel.removeAttribute('aria-hidden');
  }
  if (textarea) textarea.value = '';
  if (restoreFocus && focusTarget?.isConnected && typeof focusTarget.focus === 'function') {
    window.requestAnimationFrame(() => focusTarget.focus({ preventScroll: true }));
  }
}

function showManualCopy(text) {
  const panel = document.getElementById('manual-copy-panel');
  const textarea = document.getElementById('manual-copy-text');
  if (!panel || !textarea) return;
  textarea.value = text;
  panel.hidden = false;
  panel.removeAttribute('aria-hidden');
  panel.classList.add('show');
  window.requestAnimationFrame(() => {
    textarea.focus();
    textarea.select();
  });
}

document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && document.getElementById('manual-copy-panel')?.classList.contains('show')) {
    hideManualCopy();
  }
});

function normalizeDegradationEntry(path, value) {
  const data = value && typeof value === 'object' ? value : { label: value };
  return {
    path,
    label: String(data.label || path || 'Panel').trim(),
    source: String(data.source || path || 'unknown').trim(),
    reason: String(data.reason || 'dependency_unavailable').trim(),
  };
}

function formatDegradedEndpointBundle(entries) {
  const header = `Fallback data mode: ${entries.length} degraded endpoint(s)`;
  const lines = entries.map(entry => [
    entry.label,
    entry.path,
    `source ${entry.source}`,
    `reason ${entry.reason}`,
  ].join(' | '));
  const recoveryLines = [
    `Supabase recovery packet | ${FALLBACK_RECOVERY_PACKET_PATH}`,
    `Readiness refresh | ${FALLBACK_READINESS_REFRESH_COMMAND}`,
  ];
  return [header, ...lines, ...recoveryLines].join('\\n');
}

function clearDegradationsByPrefix(prefix) {
  for (const path of [...degradations.keys()]) {
    if (String(path).startsWith(prefix)) degradations.delete(path);
  }
}

function renderWarnings() {
  const banner = document.getElementById('dashboard-warning-banner');
  const entries = [...degradations.entries()]
    .map(([path, value]) => normalizeDegradationEntry(path, value))
    .filter(entry => entry.label);
  const labels = [...new Set(entries.map(entry => entry.label))];
  if (!entries.length) {
    banner.classList.remove('show');
    banner.innerHTML = '';
    return;
  }
  const detailRows = entries.slice(0, 12).map(entry => `<li><strong>${safeHtml(entry.label)}</strong><code>${safeHtml(entry.path)}</code><span class="dashboard-warning-meta">source ${safeHtml(entry.source)} | reason ${safeHtml(entry.reason)}</span></li>`).join('');
  const overflow = entries.length > 12 ? `<li><strong>${safeHtml(String(entries.length - 12))} more degraded panel(s)</strong></li>` : '';
  const copyBundle = formatDegradedEndpointBundle(entries);
  const recoveryHint = `<div class="dashboard-warning-recovery"><strong>Supabase recovery packet</strong><code>${safeHtml(FALLBACK_RECOVERY_PACKET_PATH)}</code><span>Readiness refresh: <code>${safeHtml(FALLBACK_READINESS_REFRESH_COMMAND)}</code></span></div>`;
  banner.innerHTML = `<div id="dashboard-warning-status" class="dashboard-warning-status" role="status" aria-live="polite" aria-atomic="true"><strong>Fallback data mode</strong><span>Some panels are using safe fallback data.</span>${labels.map(label => `<span class="dashboard-warning-chip">${safeHtml(label)}</span>`).join('')}<span class="dashboard-warning-actions" role="group" aria-label="Fallback recovery actions"><button type="button" class="operator-copy-btn" aria-label="Copy degraded endpoint details" data-copy-text="${safeHtml(copyBundle)}" onclick="copyOperatorText(this, this.dataset.copyText || '', 'Degraded endpoints copied.')">Copy endpoints</button><button type="button" class="operator-copy-btn" aria-label="Copy fallback readiness refresh command" data-copy-text="${safeHtml(FALLBACK_READINESS_REFRESH_COMMAND)}" onclick="copyOperatorText(this, this.dataset.copyText || '', 'Readiness refresh copied.')">Copy readiness refresh</button></span></div><details class="dashboard-warning-details"><summary>View degraded endpoint details</summary>${recoveryHint}<ul class="dashboard-warning-list">${detailRows}${overflow}</ul></details>`;
  banner.classList.add('show');
}

function getTapCheckoutReturnState() {
  const params = new URLSearchParams(window.location.search || '');
  const status = String(params.get('tap_checkout') || '').trim().toLowerCase();
  if (!['success', 'cancel'].includes(status)) return null;
  return {
    status,
    keyword: String(params.get('tap_keyword') || '').trim(),
    sessionId: String(params.get('tap_checkout_session_id') || params.get('session_id') || '').trim(),
  };
}

function renderTapCheckoutReturnNotice() {
  const notice = document.getElementById('tap-checkout-return-notice');
  if (!notice) return null;
  const state = getTapCheckoutReturnState();
  if (!state) {
    notice.hidden = true;
    notice.innerHTML = '';
    return null;
  }
  const success = state.status === 'success';
  const title = success ? 'Checkout success returned' : 'Checkout canceled';
  const meta = [
    state.keyword ? `Offer: ${state.keyword}` : '',
    state.sessionId ? `Session: ${state.sessionId}` : '',
  ].filter(Boolean).join(' | ');
  const verifyButton = success && state.sessionId
    ? '<button type="button" class="tap-btn tap-btn-ghost" id="tap-checkout-session-status-btn" aria-label="Verify checkout session status" onclick="verifyTapCheckoutSessionStatus(this)">Verify status</button>'
    : '';
  notice.className = `tap-checkout-return-notice ${success ? 'tap-checkout-return-success' : 'tap-checkout-return-cancel'}`;
  notice.hidden = false;
  notice.innerHTML = `<div><div class="tap-title">${safeHtml(title)}</div>${meta ? `<div class="tap-checkout-return-meta">${safeHtml(meta)}</div>` : ''}<div id="tap-checkout-session-status" class="tap-checkout-session-status" role="status" aria-live="polite" aria-atomic="true"></div></div><div class="tap-checkout-return-actions" role="group" aria-label="Checkout return actions" data-tap-checkout-return-actions="true">${verifyButton}<button type="button" class="tap-btn tap-btn-ghost" id="tap-checkout-return-clear-btn" aria-label="Clear checkout return notice" onclick="dismissTapCheckoutReturnNotice()">Clear</button></div>`;
  return state;
}

async function verifyTapCheckoutSessionStatus(button) {
  const state = getTapCheckoutReturnState();
  const statusNode = document.getElementById('tap-checkout-session-status');
  if (!state || !state.sessionId) {
    toast('Checkout session ID is missing.', 'error');
    return;
  }
  const originalText = button?.innerText || '';
  if (button) {
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    button.innerText = 'Verifying...';
  }
  try {
    const data = await fetchPanel(`/api/tap/deal-room/checkout/session/${encodeURIComponent(state.sessionId)}`, 'TAP checkout session status');
    if (!data.ok) throw new Error(data.error || 'session status unavailable');
    const summary = [
      data.checkout_status ? `checkout ${data.checkout_status}` : '',
      data.payment_status ? `payment ${data.payment_status}` : '',
      data.price_anchor ? data.price_anchor : '',
    ].filter(Boolean).join(' | ');
    const text = summary ? `Stripe status: ${summary}` : 'Stripe status returned.';
    if (statusNode) statusNode.textContent = text;
    toast(`Checkout status verified: ${summary || state.sessionId}.`);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'session status unavailable';
    if (statusNode) statusNode.textContent = `Stripe status unavailable: ${message}.`;
    toast(`Checkout status unavailable: ${message}.`, 'error');
  } finally {
    if (button) {
      button.disabled = false;
      button.setAttribute('aria-busy', 'false');
      button.innerText = originalText || 'Verify status';
    }
  }
}

function dismissTapCheckoutReturnNotice() {
  const notice = document.getElementById('tap-checkout-return-notice');
  if (notice) {
    notice.hidden = true;
    notice.innerHTML = '';
  }
  const url = new URL(window.location.href);
  ['tap_checkout', 'tap_keyword', 'tap_checkout_session_id', 'session_id'].forEach(key => url.searchParams.delete(key));
  window.history.replaceState({}, document.title, `${url.pathname}${url.search}${url.hash}`);
}

async function fetchPanel(path, label, options = undefined) {
  const response = await fetch(path, options);
  const payload = await response.json().catch(() => ({}));
  const meta = payload && typeof payload === 'object' && !Array.isArray(payload) ? payload._meta : null;
  const degraded = response.headers.get('x-dashboard-degraded') === '1' || !!(meta && meta.degraded);
  if (degraded) {
    degradations.set(path, {
      label,
      source: response.headers.get('x-dashboard-degraded-source') || meta?.source || path,
      reason: response.headers.get('x-dashboard-degraded-reason') || meta?.unavailable_reason || 'dependency_unavailable',
    });
  }
  else degradations.delete(path);
  renderWarnings();
  if (meta && payload && typeof payload === 'object' && !Array.isArray(payload)) {
    const cleaned = { ...payload };
    delete cleaned._meta;
    return cleaned;
  }
  return payload;
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function renderChart(key, elementId, config) {
  if (!window.Chart) return;
  if (charts[key]) charts[key].destroy();
  charts[key] = new ChartRuntime(document.getElementById(elementId), config);
}

async function loadStats() {
  const stats = await fetchPanel('/api/stats', 'KPI stats');
  setText('k-runs', Number(stats.total_runs || 0).toLocaleString());
  setText('k-trends', Number(stats.total_trends || 0).toLocaleString());
  setText('k-score', String(stats.avg_viral_score ?? 0));
  setText('k-tweets', Number(stats.total_tweets || 0).toLocaleString());
  const cost7 = Number(stats.llm_cost_7d || 0);
  setText('k-cost', `$${cost7.toFixed(4)}`);
  setText('k-cost-sub', `Monthly estimate $${((cost7 / 7) * 30).toFixed(2)}`);
  if (Array.isArray(stats.llm_daily) && stats.llm_daily.length) {
    renderChart('cost', 'chart-cost', { type: 'bar', data: { labels: stats.llm_daily.map(row => String(row.date || '').slice(5)), datasets: [{ label: 'USD', data: stats.llm_daily.map(row => Number(row.cost_usd || 0)), backgroundColor: C.indigo + '66', borderColor: C.indigo, borderWidth: 1 }] }, options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, grid: { color: C.grid } } } } });
  }
}

async function loadPipeline() {
  const status = await fetch('/api/pipeline_status').then(res => res.json()).catch(() => ({ state: 'error' }));
  const pill = document.getElementById('status-pill');
  const states = { idle: ['Idle', 'st-idle'], running: ['Running', 'st-running'], error: ['Error', 'st-error'] };
  const [label, cls] = states[status.state] || ['Unknown', 'st-idle'];
  pill.textContent = label;
  pill.className = `status-pill ${cls}`;
  if (status.last_run_at) pill.title = `Last run ${String(status.last_run_at).slice(0, 16)}`;
  const budget = status.budget || {};
  if (Number(budget.daily_budget_usd || 0) > 0) {
    const used = Number(budget.today_cost_usd || 0);
    const budgetUsd = Number(budget.daily_budget_usd);
    const pct = Math.min(Number(budget.budget_used_pct || 0), 100);
    setText('k-budget', `$${used.toFixed(4)}`);
    setText('k-budget-sub', `/ $${budgetUsd.toFixed(2)}`);
    const bar = document.getElementById('k-budget-bar');
    bar.style.width = `${pct}%`;
    bar.className = `budget-fill ${pct >= 80 ? 'warn' : ''}`;
  }
}

async function loadTrends() {
  const trends = await fetchPanel('/api/trends?days=7&limit=200', 'Trend timeline');
  const rows = Array.isArray(trends) ? trends : [];
  const scores = rows.map(row => Number(row.viral_potential || 0));
  renderChart('timeline', 'chart-timeline', { type: 'bar', data: { labels: rows.map(row => String(row.scored_at || '').slice(5, 16)), datasets: [{ data: scores, backgroundColor: scores.map(score => score >= 80 ? C.green + '66' : score >= 65 ? C.amber + '66' : C.red + '66'), borderWidth: 0 }] }, options: { responsive: true, plugins: { legend: { display: false } }, scales: { x: { display: false }, y: { beginAtZero: true, max: 100, grid: { color: C.grid } } } } });
  const sorted = [...rows].sort((a, b) => Number(b.trend_acceleration || 0) - Number(a.trend_acceleration || 0)).slice(0, 10);
  renderChart('accel', 'chart-accel', { type: 'bar', data: { labels: sorted.map(row => String(row.keyword || '').slice(0, 14)), datasets: [{ data: sorted.map(row => Number(row.trend_acceleration || 0)), backgroundColor: PALETTE.map(color => color + '66') }] }, options: { responsive: true, indexAxis: 'y', plugins: { legend: { display: false } }, scales: { x: { grid: { color: C.grid } }, y: { grid: { display: false } } } } });
  const body = document.getElementById('t-body');
  body.innerHTML = rows.slice(0, 50).map((row, index) => {
    const score = Number(row.viral_potential || 0);
    const cls = score >= 80 ? 'score-high' : score >= 65 ? 'score-mid' : 'score-low';
    return `<tr><td>${index + 1}</td><td>${safeHtml(row.keyword || '')}</td><td class="${cls}">${score}</td><td>${safeHtml(row.country || '')}</td><td>${safeHtml(row.trend_acceleration ?? '-')}</td><td>${safeHtml(row.top_insight || '-')}</td><td>${safeHtml(String(row.scored_at || '').slice(0, 16) || '-')}</td></tr>`;
  }).join('') || '<tr><td colspan="7">No scored trends yet.</td></tr>';
}

async function loadCategories() {
  const categories = await fetchPanel('/api/stats/categories?days=7', 'Category mix');
  const rows = Array.isArray(categories) ? categories : [];
  renderChart('category', 'chart-category', { type: 'doughnut', data: { labels: rows.map(row => row.category || 'Other'), datasets: [{ data: rows.map(row => Number(row.count || 0)), backgroundColor: PALETTE.map(color => color + '88') }] }, options: { responsive: true, cutout: '62%', plugins: { legend: { position: 'bottom' } } } });
}

async function loadSourceQuality() {
  const quality = await fetchPanel('/api/source/quality?days=7', 'Source quality');
  const sources = Object.keys(quality || {});
  renderChart('source', 'chart-source', { type: 'radar', data: { labels: sources, datasets: [{ label: 'Success rate (%)', data: sources.map(source => Number(quality[source].success_rate || 0)), borderColor: C.green, backgroundColor: C.green + '22' }, { label: 'Quality score', data: sources.map(source => Number(quality[source].avg_quality_score || 0) * 100), borderColor: C.sky, backgroundColor: C.sky + '22' }] }, options: { responsive: true, scales: { r: { beginAtZero: true, max: 100, grid: { color: C.grid } } }, plugins: { legend: { position: 'bottom' } } } });
}

async function loadLogs() {
  const data = await fetch('/api/logs?limit=50').then(res => res.json()).catch(() => ({ logs: [] }));
  const logs = Array.isArray(data.logs) ? data.logs : [];
  document.getElementById('log-viewer').innerHTML = logs.length ? logs.map(line => `<div>${safeHtml(line)}</div>`).join('') : '<div style="color:#64748b">No live logs yet.</div>';
}

async function loadAbTest() {
  const data = await fetch('/api/ab_test').then(res => res.json()).catch(() => ({ metrics: {} }));
  const a = data.metrics?.group_a || { ctr: 0, conversion: 0 };
  const b = data.metrics?.group_b || { ctr: 0, conversion: 0 };
  const winA = Number(a.conversion || 0) >= Number(b.conversion || 0);
  document.getElementById('ab-test-content').innerHTML = [
    { label: 'Control (Group A)', data: a, winner: winA },
    { label: 'Variant (Group B)', data: b, winner: !winA },
  ].map(item => `<div class="tap-card"><div class="tap-title">${item.label} ${item.winner ? '(winner)' : ''}</div><div class="value">${safeHtml(item.data.ctr ?? 0)}%</div><div class="tap-copy">Conversion ${safeHtml(item.data.conversion ?? 0)}%</div></div>`).join('');
}

function operatorStateClass(state) {
  const normalized = String(state || '').toLowerCase();
  if (['pass', 'success', 'ok'].includes(normalized)) return 'operator-pass';
  if (['warn', 'warning', 'stale'].includes(normalized)) return 'operator-warn';
  if (['fail', 'error', 'missing'].includes(normalized)) return 'operator-fail';
  return 'operator-unknown';
}

async function copyOperatorAction(button) {
  const action = button?.closest('.operator-action');
  const code = action?.querySelector('code');
  const text = (code?.innerText || '').trim();
  await copyOperatorText(button, text, 'Action copied.');
}

function getOperatorCopyOriginalText(button) {
  if (!button) return 'Copy';
  const stored = button.dataset.copyOriginalText;
  if (stored) return stored;
  const currentText = (button.innerText || '').trim() || 'Copy';
  button.dataset.copyOriginalText = currentText;
  return currentText;
}

function setOperatorCopyFeedback(button, label) {
  if (!button) return;
  const originalText = getOperatorCopyOriginalText(button);
  const existingTimer = operatorCopyResetTimers.get(button);
  if (existingTimer) window.clearTimeout(existingTimer);
  button.innerText = label;
  const resetTimer = window.setTimeout(() => {
    button.innerText = originalText;
    operatorCopyResetTimers.delete(button);
  }, OPERATOR_COPY_RESET_DELAY_MS);
  operatorCopyResetTimers.set(button, resetTimer);
}

async function copyOperatorText(button, text, message = 'Copied.') {
  const normalizedText = String(text || '').replace(/\\\\n/g, '\\n');
  if (!normalizedText) return;
  let copied = false;
  const canUseAsyncClipboard = Boolean(navigator.clipboard?.writeText);
  if (canUseAsyncClipboard) {
    try {
      await navigator.clipboard.writeText(normalizedText);
      copied = true;
    } catch {}
  }
  if (!copied && !canUseAsyncClipboard) {
    const textarea = document.createElement('textarea');
    textarea.value = normalizedText;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    textarea.style.pointerEvents = 'none';
    document.body.appendChild(textarea);
    textarea.select();
    try {
      copied = document.execCommand('copy');
    } catch {}
    document.body.removeChild(textarea);
  }
  button.dataset.copyResult = copied ? 'copied' : 'failed';
  setOperatorCopyFeedback(button, copied ? 'Copied' : 'Failed');
  if (copied) {
    hideManualCopy({ restoreFocus: false });
    toast(message);
  } else {
    manualCopyFocusTarget = button && typeof button.focus === 'function' ? button : null;
    showManualCopy(normalizedText);
    toast('Copy failed. Select the text and copy manually.', 'error');
  }
}

function markOperatorCopyFailed(button, message = 'Copy source unavailable.') {
  if (!button) return;
  button.dataset.copyResult = 'failed';
  setOperatorCopyFeedback(button, 'Failed');
  toast(message, 'error');
}

async function copyOperatorRecoveryBundle(button) {
  const action = button?.closest('.operator-action');
  const packetPath = (action?.querySelector('code')?.innerText || '').trim();
  if (!packetPath) return markOperatorCopyFailed(button, 'Recovery packet path unavailable.');
  try {
    const data = await fetch(`/api/operator/recovery-packet?path=${encodeURIComponent(packetPath)}`).then(res => res.json());
    const packet = data.packet && typeof data.packet === 'object' ? data.packet : {};
    const recoveryBundle = typeof packet.recovery_bundle === 'string' && packet.recovery_bundle.trim() ? packet.recovery_bundle.trim() : '';
    if (!recoveryBundle) return markOperatorCopyFailed(button, 'Recovery bundle unavailable.');
    await copyOperatorText(button, recoveryBundle, 'Recovery bundle copied.');
  } catch {
    markOperatorCopyFailed(button, 'Recovery bundle unavailable.');
  }
}

async function copyOperatorRecoveryVerify(button) {
  const action = button?.closest('.operator-action');
  const packetPath = (action?.querySelector('code')?.innerText || '').trim();
  if (!packetPath) return markOperatorCopyFailed(button, 'Recovery packet path unavailable.');
  try {
    const data = await fetch(`/api/operator/recovery-packet?path=${encodeURIComponent(packetPath)}`).then(res => res.json());
    const packet = data.packet && typeof data.packet === 'object' ? data.packet : {};
    const commands = Array.isArray(packet.verification_commands) ? packet.verification_commands.filter(Boolean) : [];
    const commandBundle = typeof packet.verification_command_bundle === 'string' && packet.verification_command_bundle.trim() ? packet.verification_command_bundle.trim() : '';
    const commandText = commandBundle || commands.join('\\n');
    if (!commandText) return markOperatorCopyFailed(button, 'Recovery verification unavailable.');
    await copyOperatorText(button, commandText, 'Recovery verification copied.');
  } catch {
    markOperatorCopyFailed(button, 'Recovery verification unavailable.');
  }
}

async function copyOperatorRecoverySuccess(button) {
  const action = button?.closest('.operator-action');
  const packetPath = (action?.querySelector('code')?.innerText || '').trim();
  if (!packetPath) return markOperatorCopyFailed(button, 'Recovery packet path unavailable.');
  try {
    const data = await fetch(`/api/operator/recovery-packet?path=${encodeURIComponent(packetPath)}`).then(res => res.json());
    const packet = data.packet && typeof data.packet === 'object' ? data.packet : {};
    const criteria = Array.isArray(packet.launch_success_criteria) ? packet.launch_success_criteria.filter(Boolean) : [];
    if (!criteria.length) return markOperatorCopyFailed(button, 'Launch success criteria unavailable.');
    const criteriaText = ['Launch success criteria:', ...criteria.map((item, index) => `${index + 1}. ${item}`)].join('\\n');
    await copyOperatorText(button, criteriaText, 'Launch success criteria copied.');
  } catch {
    markOperatorCopyFailed(button, 'Launch success criteria unavailable.');
  }
}

async function copyOperatorRecoveryPacketTextField(button, fieldName, unavailableMessage, successMessage) {
  const action = button?.closest('.operator-action');
  const packetPath = (action?.querySelector('code')?.innerText || '').trim();
  if (!packetPath) return markOperatorCopyFailed(button, 'Recovery packet path unavailable.');
  try {
    const data = await fetch(`/api/operator/recovery-packet?path=${encodeURIComponent(packetPath)}`).then(res => res.json());
    const packet = data.packet && typeof data.packet === 'object' ? data.packet : {};
    const text = typeof packet[fieldName] === 'string' && packet[fieldName].trim() ? packet[fieldName].trim() : '';
    if (!text) return markOperatorCopyFailed(button, unavailableMessage);
    await copyOperatorText(button, text, successMessage);
  } catch {
    markOperatorCopyFailed(button, unavailableMessage);
  }
}

async function copyOperatorSchedulerPauseCommands(button) {
  await copyOperatorRecoveryPacketTextField(
    button,
    'scheduler_pause_command_bundle',
    'Scheduler pause commands unavailable.',
    'Scheduler pause commands copied.'
  );
}

async function copyOperatorCredentialUpdateCommands(button) {
  await copyOperatorRecoveryPacketTextField(
    button,
    'credential_update_command_bundle',
    'Credential update commands unavailable.',
    'Credential update commands copied.'
  );
}

async function copyOperatorSchedulerResumeCommands(button) {
  await copyOperatorRecoveryPacketTextField(
    button,
    'scheduler_resume_command_bundle',
    'Scheduler resume commands unavailable.',
    'Scheduler resume commands copied.'
  );
}

async function loadOperatorRecoveryPacket(button) {
  const action = button?.closest('.operator-action');
  const preview = action?.querySelector('.operator-packet-preview');
  if (!preview) return;
  if (collapseOperatorPreview(button, preview)) return;
  setOperatorDisclosureState(button, preview, true);
  setOperatorPreviewBusy(button, preview, true);
  preview.innerHTML = '<span>Loading packet</span>';
  try {
    const packetPath = (action?.querySelector('code')?.innerText || '').trim();
    const packetUrl = packetPath ? `/api/operator/recovery-packet?path=${encodeURIComponent(packetPath)}` : '/api/operator/recovery-packet';
    const data = await fetch(packetUrl).then(res => res.json());
    const packet = data.packet && typeof data.packet === 'object' ? data.packet : {};
    const fullIssues = Array.isArray(packet.issue_types) ? packet.issue_types.filter(Boolean) : [];
    const issues = fullIssues.slice(0, 6);
    const env = Array.isArray(packet.required_env) ? packet.required_env.filter(Boolean).slice(0, 4) : [];
    const fullChecklist = Array.isArray(packet.recovery_checklist) ? packet.recovery_checklist.filter(Boolean) : [];
    const checklist = fullChecklist.slice(0, 3);
    const fullConnectionFacts = Array.isArray(packet.connection_mode_facts) ? packet.connection_mode_facts.filter(Boolean) : [];
    const connectionFacts = fullConnectionFacts.slice(0, 7);
    const recoverySafetyPattern = new RegExp('pause scheduled/background|getdaytrends clients|circuit breaker|wait at least 2 minutes', 'i');
    const recoverySafetyChecklist = fullChecklist
      .filter(item => recoverySafetyPattern.test(String(item || '')))
      .slice(0, 3);
    const successCriteria = Array.isArray(packet.launch_success_criteria) ? packet.launch_success_criteria.filter(Boolean) : [];
    const postCredentialSequence = Array.isArray(packet.post_credential_recheck_sequence) ? packet.post_credential_recheck_sequence.filter(item => item && typeof item === 'object') : [];
    const postCredentialEvidence = Array.isArray(packet.post_credential_recheck_evidence) ? packet.post_credential_recheck_evidence.filter(item => item && typeof item === 'object') : [];
    const operatorFinalProofBundle = Array.isArray(packet.operator_final_proof_bundle) ? packet.operator_final_proof_bundle.filter(item => item && typeof item === 'object') : [];
    const referenceLinks = Array.isArray(packet.reference_links) ? packet.reference_links.filter(item => item && typeof item === 'object').slice(0, 5) : [];
    const diagnostics = Array.isArray(packet.diagnostics) ? packet.diagnostics.filter(Boolean) : [];
    const packetGenerated = typeof packet.generated_at === 'string' && packet.generated_at.trim() ? packet.generated_at : '';
    const readinessGenerated = typeof packet.readiness_generated_at === 'string' && packet.readiness_generated_at.trim() ? packet.readiness_generated_at : '';
    const nextAction = typeof packet.next_required_action === 'string' && packet.next_required_action.trim() ? packet.next_required_action.trim() : '';
    const operatorFocus = typeof packet.operator_focus === 'string' && packet.operator_focus.trim() ? packet.operator_focus.trim() : '';
    const fullBlockingChecks = Array.isArray(packet.blocking_checks) ? packet.blocking_checks.map(check => check && check.name).filter(Boolean) : [];
    const blockingChecks = fullBlockingChecks.slice(0, 6);
    const sourceChecks = packet.source_checks && typeof packet.source_checks === 'object' ? packet.source_checks : {};
    const cliSourceCheck = sourceChecks.cli_smoke_report && typeof sourceChecks.cli_smoke_report === 'object' ? sourceChecks.cli_smoke_report : {};
    const providerSourceCheck = sourceChecks.provider_auth_report && typeof sourceChecks.provider_auth_report === 'object' ? sourceChecks.provider_auth_report : {};
    const runtimeFallbackCount = Number.isFinite(Number(cliSourceCheck.runtime_fallback_count)) ? Number(cliSourceCheck.runtime_fallback_count) : null;
    const providerAuthFailureCount = Number.isFinite(Number(providerSourceCheck.provider_auth_failure_count)) ? Number(providerSourceCheck.provider_auth_failure_count) : null;
    const generatedText = [
      packetGenerated ? `Packet ${packetGenerated}` : '',
      readinessGenerated ? `Readiness ${readinessGenerated}` : '',
    ].filter(Boolean).join(' | ');
    const checklistText = [
      env.length ? `Required env: ${env.join(', ')}` : '',
      fullConnectionFacts.length ? 'Connection mode facts:' : '',
      ...fullConnectionFacts,
      ...fullChecklist,
    ].filter(Boolean).join('\\n');
    const connectionFactsText = fullConnectionFacts.length ? fullConnectionFacts.join('\\n') : '';
    const commands = Array.isArray(packet.verification_commands) ? packet.verification_commands.filter(Boolean) : [];
    const commandBundle = typeof packet.verification_command_bundle === 'string' && packet.verification_command_bundle.trim() ? packet.verification_command_bundle : '';
    const commandText = commandBundle || commands.join('\\n');
    const credentialUpdateCommandBundle = typeof packet.credential_update_command_bundle === 'string' && packet.credential_update_command_bundle.trim() ? packet.credential_update_command_bundle.trim() : '';
    const credentialUpdateCommands = Array.isArray(packet.credential_update_commands) ? packet.credential_update_commands.filter(Boolean) : [];
    const credentialUpdateText = credentialUpdateCommandBundle || credentialUpdateCommands.join('\\n');
    const schedulerPauseCommandBundle = typeof packet.scheduler_pause_command_bundle === 'string' && packet.scheduler_pause_command_bundle.trim() ? packet.scheduler_pause_command_bundle.trim() : '';
    const schedulerResumeCommandBundle = typeof packet.scheduler_resume_command_bundle === 'string' && packet.scheduler_resume_command_bundle.trim() ? packet.scheduler_resume_command_bundle.trim() : '';
    const formatRecheckStep = (item, index) => {
      const step = String(item.step || `step_${index + 1}`).trim();
      const command = String(item.command || '').trim();
      const success = String(item.success_criterion || '').trim();
      return `${index + 1}. ${step}${command ? ` | ${command}` : ''}${success ? ` | ${success}` : ''}`;
    };
    const formatEvidenceItem = (item, index) => {
      const step = String(item.step || `evidence_${index + 1}`).trim();
      const artifact = String(item.artifact || '').trim();
      const signal = String(item.success_signal || '').trim();
      return `${index + 1}. ${step}${artifact ? ` | ${artifact}` : ''}${signal ? ` | ${signal}` : ''}`;
    };
    const formatProofItem = (item, index) => {
      const artifact = String(item.artifact || `artifact_${index + 1}`).trim();
      const signal = String(item.success_signal || '').trim();
      return `${index + 1}. ${artifact}${signal ? ` | ${signal}` : ''}`;
    };
    const postCredentialSequenceText = postCredentialSequence.map(formatRecheckStep).join('\\n');
    const postCredentialEvidenceText = postCredentialEvidence.map(formatEvidenceItem).join('\\n');
    const postCredentialRecheckText = [
      postCredentialSequenceText ? 'Post-credential recheck sequence:' : '',
      postCredentialSequenceText,
      postCredentialEvidenceText ? 'Post-credential evidence artifacts:' : '',
      postCredentialEvidenceText,
    ].filter(Boolean).join('\\n');
    const finalProofText = operatorFinalProofBundle.length ? ['Operator final proof bundle:', ...operatorFinalProofBundle.map(formatProofItem)].join('\\n') : '';
    const recheckStepNames = postCredentialSequence.map(item => String(item.step || '').trim()).filter(Boolean);
    const recheckEvidenceArtifacts = postCredentialEvidence.map(item => String(item.artifact || '').trim()).filter(Boolean);
    const finalProofArtifacts = operatorFinalProofBundle.map(item => String(item.artifact || '').trim()).filter(Boolean);
    const finalProofSignals = operatorFinalProofBundle.map(item => String(item.success_signal || '').trim()).filter(Boolean);
    const commandLines = commandText ? commandText.split(/\\r?\\n/).map(line => String(line || '').trim()).filter(Boolean) : [];
    const verificationCwdLine = commandLines.find(line => line.startsWith('Set-Location -LiteralPath ')) || '';
    const verificationCwd = verificationCwdLine
      ? verificationCwdLine.replace(/^Set-Location -LiteralPath\\s+/, '').replace(/^'|'$/g, '').replace(/''/g, "'")
      : '';
    const previewCommands = (commands.length ? commands : commandLines.filter(line => !line.startsWith('Set-Location -LiteralPath '))).slice(0, 3);
    const envTemplate = typeof packet.env_template === 'string' && packet.env_template.trim() ? packet.env_template : '';
    const recoveryBundle = typeof packet.recovery_bundle === 'string' && packet.recovery_bundle.trim() ? packet.recovery_bundle : '';
    const actionButtons = [
      nextAction ? `<button type="button" class="operator-copy-btn" aria-label="Copy recovery next action" data-copy-text="${safeHtml(nextAction)}" onclick="copyOperatorText(this, this.dataset.copyText || '', 'Recovery next action copied.')">Copy recovery next action</button>` : '',
      connectionFactsText ? `<button type="button" class="operator-copy-btn" aria-label="Copy connection mode facts" data-copy-text="${safeHtml(connectionFactsText)}" onclick="copyOperatorText(this, this.dataset.copyText || '', 'Connection facts copied.')">Copy connection facts</button>` : '',
      schedulerPauseCommandBundle ? `<button type="button" class="operator-copy-btn" aria-label="Copy scheduler pause commands" data-copy-text="${safeHtml(schedulerPauseCommandBundle)}" onclick="copyOperatorText(this, this.dataset.copyText || '', 'Scheduler pause commands copied.')">Copy scheduler pause commands</button>` : '',
      credentialUpdateText ? `<button type="button" class="operator-copy-btn" aria-label="Copy credential update commands" data-copy-text="${safeHtml(credentialUpdateText)}" onclick="copyOperatorText(this, this.dataset.copyText || '', 'Credential update commands copied.')">Copy credential update commands</button>` : '',
      postCredentialRecheckText ? `<button type="button" class="operator-copy-btn" aria-label="Copy post-credential recheck sequence" data-copy-text="${safeHtml(postCredentialRecheckText)}" onclick="copyOperatorText(this, this.dataset.copyText || '', 'Post-credential recheck copied.')">Copy post-credential recheck</button>` : '',
      finalProofText ? `<button type="button" class="operator-copy-btn" aria-label="Copy operator final proof bundle" data-copy-text="${safeHtml(finalProofText)}" onclick="copyOperatorText(this, this.dataset.copyText || '', 'Operator final proof copied.')">Copy final proof bundle</button>` : '',
      recoveryBundle ? `<button type="button" class="operator-copy-btn operator-copy-btn-primary" aria-label="Copy complete recovery bundle" data-copy-priority="primary" title="Recommended recovery handoff" data-copy-text="${safeHtml(recoveryBundle)}" onclick="copyOperatorText(this, this.dataset.copyText || '', 'Recovery bundle copied.')">Copy recovery bundle</button>` : '',
      envTemplate ? `<button type="button" class="operator-copy-btn" aria-label="Copy recovery env template" data-copy-text="${safeHtml(envTemplate)}" onclick="copyOperatorText(this, this.dataset.copyText || '', 'Recovery env template copied.')">Copy recovery env template</button>` : '',
      checklistText ? `<button type="button" class="operator-copy-btn" aria-label="Copy recovery checklist" data-copy-text="${safeHtml(checklistText)}" onclick="copyOperatorText(this, this.dataset.copyText || '', 'Recovery checklist copied.')">Copy recovery checklist</button>` : '',
      schedulerResumeCommandBundle ? `<button type="button" class="operator-copy-btn" aria-label="Copy scheduler resume commands" data-copy-text="${safeHtml(schedulerResumeCommandBundle)}" onclick="copyOperatorText(this, this.dataset.copyText || '', 'Scheduler resume commands copied.')">Copy scheduler resume commands</button>` : '',
      commands.length ? `<button type="button" class="operator-copy-btn" aria-label="Copy recovery verification commands" data-copy-text="${safeHtml(commandText)}" onclick="copyOperatorText(this, this.dataset.copyText || '', 'Verification commands copied.')">Copy recovery verification commands</button>` : '',
    ].filter(Boolean).join('');
    const actionGroup = actionButtons ? `<span class="operator-packet-action-group" role="group" aria-label="Recovery packet copy actions">${actionButtons}</span>` : '';
    preview.innerHTML = [
      `<span>Packet status: ${safeHtml(data.status || packet.status || 'unknown')}</span>`,
      generatedText ? `<span>Generated: ${safeHtml(generatedText)}</span>` : '',
      nextAction ? `<span>Next action: ${safeHtml(nextAction)}</span>` : '',
      operatorFocus ? `<span>Operator focus: ${safeHtml(operatorFocus)}</span>` : '',
      issues.length ? `<span>Issue types: ${safeHtml(issues.join(', '))}</span>` : '',
      fullIssues.length ? `<span>Issue count: ${safeHtml(String(fullIssues.length))}</span>` : '',
      blockingChecks.length ? `<span>Blocking checks: ${safeHtml(blockingChecks.join(', '))}</span>` : '',
      fullBlockingChecks.length ? `<span>Blocking check count: ${safeHtml(String(fullBlockingChecks.length))}</span>` : '',
      runtimeFallbackCount !== null ? `<span>Runtime fallbacks: ${safeHtml(String(runtimeFallbackCount))}</span>` : '',
      providerAuthFailureCount !== null ? `<span>Provider auth failures: ${safeHtml(String(providerAuthFailureCount))}</span>` : '',
      diagnostics.length ? `<span>Doctor diagnostics: ${safeHtml(String(diagnostics.length))}</span>` : '',
      env.length ? `<span>Required env: ${safeHtml(env.join(', '))}</span>` : '',
      connectionFacts.length ? `<span>Connection facts: ${safeHtml(connectionFacts.join(' | '))}</span>` : '',
      recoverySafetyChecklist.length ? `<span>Recovery safety: ${safeHtml(recoverySafetyChecklist.join(' | '))}</span>` : '',
      schedulerPauseCommandBundle ? `<span>Scheduler control: pause known getdaytrends scheduled tasks before DB credential rotation, then resume only after launch gates pass.</span>` : '',
      renderOperatorReferenceLinks(referenceLinks),
      verificationCwd ? `<span>Verification cwd: ${safeHtml(verificationCwd)}</span>` : '',
      successCriteria.length ? `<span>Launch success: ${safeHtml(successCriteria.join(' | '))}</span>` : '',
      recheckStepNames.length ? `<span>Post-credential recheck: ${safeHtml(recheckStepNames.join(' -> '))}</span>` : '',
      recheckEvidenceArtifacts.length ? `<span>Recheck evidence: ${safeHtml(recheckEvidenceArtifacts.slice(0, 5).join(' | '))}${recheckEvidenceArtifacts.length > 5 ? safeHtml(` | +${recheckEvidenceArtifacts.length - 5} more`) : ''}</span>` : '',
      finalProofArtifacts.length ? `<span>Final proof: ${safeHtml(String(finalProofArtifacts.length))} artifact(s) | ${safeHtml(finalProofArtifacts.slice(0, 5).join(' | '))}${finalProofArtifacts.length > 5 ? safeHtml(` | +${finalProofArtifacts.length - 5} more`) : ''}</span>` : '',
      finalProofSignals.length ? `<span>Final proof signals: ${safeHtml(finalProofSignals.slice(0, 4).join(' | '))}${finalProofSignals.length > 4 ? safeHtml(` | +${finalProofSignals.length - 4} more`) : ''}</span>` : '',
      checklist.length ? `<span>Checklist: ${safeHtml(checklist.join(' | '))}</span>` : '',
      previewCommands.length ? `<span>Verify: ${safeHtml(previewCommands.join(' | '))}${commands.length > previewCommands.length ? safeHtml(` | +${commands.length - previewCommands.length} more`) : ''}</span>` : '',
      actionGroup,
    ].filter(Boolean).join('');
  } catch {
    preview.innerHTML = '<span>Packet unavailable</span>';
  } finally {
    setOperatorPreviewBusy(button, preview, false);
  }
}

async function loadOperatorWorkspaceSmoke(button) {
  const action = button?.closest('.operator-action');
  const preview = action?.querySelector('.operator-workspace-smoke-preview');
  if (!preview) return;
  if (collapseOperatorPreview(button, preview)) return;
  setOperatorDisclosureState(button, preview, true);
  setOperatorPreviewBusy(button, preview, true);
  preview.innerHTML = '<span>Loading workspace smoke</span>';
  try {
    const requestedArtifactPath = String(button?.dataset?.artifactPath || action?.querySelector('code')?.innerText || '').trim();
    const endpoint = requestedArtifactPath ? `/api/operator/workspace-smoke?path=${encodeURIComponent(requestedArtifactPath)}` : '/api/operator/workspace-smoke';
    const data = await fetch(endpoint).then(res => res.json());
    const summary = data.summary && typeof data.summary === 'object' ? data.summary : {};
    const failed = Array.isArray(data.failed_checks) ? data.failed_checks.filter(Boolean).slice(0, 6) : [];
    const failedDetails = Array.isArray(data.failed_details) ? data.failed_details.filter(Boolean).slice(0, 3) : [];
    const failedRerunBundle = typeof data.failed_rerun_command_bundle === 'string' && data.failed_rerun_command_bundle.trim() ? data.failed_rerun_command_bundle.trim() : '';
    const failedRerunCommands = Array.isArray(data.failed_rerun_commands) ? data.failed_rerun_commands.filter(Boolean) : [];
    const failedRerunText = failedRerunBundle || failedRerunCommands.join('\\n');
    const generatedAt = typeof data.generated_at === 'string' && data.generated_at.trim() ? data.generated_at.trim() : '';
    const artifactPath = typeof data.path === 'string' && data.path.trim() ? data.path.trim() : '';
    const rawStatus = typeof data.status === 'string' && data.status.trim() ? data.status.trim() : 'unknown';
    const conclusion = typeof data.conclusion === 'string' && data.conclusion.trim() ? data.conclusion.trim() : rawStatus;
    const total = Number(summary.total || 0);
    const passed = Number(summary.passed || 0);
    const failedCount = Number(summary.failed || 0);
    const detailRows = failedDetails.flatMap((detail) => {
      const name = typeof detail.name === 'string' && detail.name.trim() ? detail.name.trim() : 'unknown check';
      const command = typeof detail.command === 'string' && detail.command.trim() ? detail.command.trim() : '';
      const stdout = typeof detail.stdout_tail === 'string' && detail.stdout_tail.trim() ? detail.stdout_tail.trim() : '';
      const stderr = typeof detail.stderr_tail === 'string' && detail.stderr_tail.trim() ? detail.stderr_tail.trim() : '';
      const output = [stdout, stderr].filter(Boolean).join('\\n');
      const returncode = detail.returncode === 0 || detail.returncode ? ` (exit ${detail.returncode})` : '';
      return [
        `<span>Detail: ${safeHtml(name)}${safeHtml(returncode)}</span>`,
        command ? `<span>Command: <code>${safeHtml(command)}</code></span>` : '',
        output ? `<span>Output: <samp>${safeHtml(output)}</samp></span>` : '',
      ].filter(Boolean);
    });
    const actionButtons = failedRerunText
      ? `<span class="operator-packet-action-group" role="group" aria-label="Workspace smoke copy actions"><button type="button" class="operator-copy-btn operator-copy-btn-primary" aria-label="Copy failed workspace smoke command" data-copy-priority="primary" data-copy-text="${safeHtml(failedRerunText)}" onclick="copyOperatorText(this, this.dataset.copyText || '', 'Failed workspace command copied.')">Copy failed command</button></span>`
      : '';
    preview.innerHTML = [
      `<span>Workspace smoke: ${safeHtml(conclusion)}</span>`,
      rawStatus !== conclusion ? `<span>Run status: ${safeHtml(rawStatus)}</span>` : '',
      generatedAt ? `<span>Generated: <time datetime="${safeHtml(generatedAt)}">${safeHtml(generatedAt)}</time></span>` : '',
      artifactPath ? `<span>Artifact: ${safeHtml(artifactPath)}</span>` : '',
      total ? `<span>Summary: ${safeHtml(`${passed}/${total} passed, ${failedCount} failed`)}</span>` : '',
      failed.length ? `<span>Failed checks: ${safeHtml(failed.join(', '))}</span>` : '',
      ...detailRows,
      actionButtons,
    ].filter(Boolean).join('');
  } catch {
    preview.innerHTML = '<span>Workspace smoke unavailable</span>';
  } finally {
    setOperatorPreviewBusy(button, preview, false);
  }
}

async function loadOperatorLaunchSecretScan(button) {
  const action = button?.closest('.operator-action');
  const preview = action?.querySelector('.operator-launch-secret-scan-preview');
  if (!preview) return;
  if (collapseOperatorPreview(button, preview)) return;
  setOperatorDisclosureState(button, preview, true);
  setOperatorPreviewBusy(button, preview, true);
  preview.innerHTML = '<span>Loading launch secret scan</span>';
  try {
    const requestedArtifactPath = String(button?.dataset?.artifactPath || action?.querySelector('code')?.innerText || '').trim();
    const endpoint = requestedArtifactPath ? `/api/operator/launch-secret-scan?path=${encodeURIComponent(requestedArtifactPath)}` : '/api/operator/launch-secret-scan';
    const data = await fetch(endpoint).then(res => res.json());
    const summary = data.summary && typeof data.summary === 'object' ? data.summary : {};
    const generatedAt = typeof data.generated_at === 'string' && data.generated_at.trim() ? data.generated_at.trim() : '';
    const artifactPath = typeof data.path === 'string' && data.path.trim() ? data.path.trim() : '';
    const scope = typeof data.scope === 'string' && data.scope.trim() ? data.scope.trim() : '';
    const status = typeof data.status === 'string' && data.status.trim() ? data.status.trim() : 'unknown';
    const scanned = Number(summary.scanned || 0);
    const findings = Number(summary.findings || 0);
    const missing = Number(summary.missing || 0);
    const includeCurrent = data.include_current_artifacts === true;
    const findingPatterns = Array.isArray(data.finding_patterns) ? data.finding_patterns.map(item => String(item || '').trim()).filter(Boolean).slice(0, 8) : [];
    const missingPaths = Array.isArray(data.missing_paths) ? data.missing_paths.map(item => String(item || '').trim()).filter(Boolean).slice(0, 8) : [];
    const scannedSample = Array.isArray(data.scanned_sample) ? data.scanned_sample.map(item => String(item || '').trim()).filter(Boolean).slice(0, 8) : [];
    const currentArtifactSample = Array.isArray(data.current_artifact_sample) ? data.current_artifact_sample.map(item => String(item || '').trim()).filter(Boolean).slice(0, 8) : [];
    const refreshCommand = typeof data.refresh_command === 'string' && data.refresh_command.trim() ? data.refresh_command.trim() : '';
    const summaryText = [
      `Launch secret scan: ${status}`,
      generatedAt ? `Generated: ${generatedAt}` : '',
      artifactPath ? `Artifact: ${artifactPath}` : '',
      scope ? `Scope: ${scope}` : '',
      `Current artifacts: ${includeCurrent ? 'included' : 'not included'}`,
      `Summary: ${scanned} scanned, ${findings} findings, ${missing} missing`,
      findingPatterns.length ? `Finding patterns: ${findingPatterns.join(', ')}` : '',
      missingPaths.length ? `Missing paths: ${missingPaths.join(', ')}` : '',
      currentArtifactSample.length ? `Current artifact sample: ${currentArtifactSample.join(', ')}` : '',
      refreshCommand ? `Refresh: ${refreshCommand}` : '',
    ].filter(Boolean).join('\\n');
    const actionButtons = [
      summaryText ? `<button type="button" class="operator-copy-btn" aria-label="Copy launch secret scan summary" data-copy-text="${safeHtml(summaryText)}" onclick="copyOperatorText(this, this.dataset.copyText || '', 'Launch secret scan summary copied.')">Copy scan summary</button>` : '',
      refreshCommand ? `<button type="button" class="operator-copy-btn" aria-label="Copy launch secret scan preview refresh command" data-copy-text="${safeHtml(refreshCommand)}" onclick="copyOperatorText(this, this.dataset.copyText || '', 'Launch secret scan refresh copied.')">Copy refresh command</button>` : '',
    ].filter(Boolean).join('');
    preview.innerHTML = [
      `<span>Launch secret scan: ${safeHtml(status)}</span>`,
      generatedAt ? `<span>Generated: <time datetime="${safeHtml(generatedAt)}">${safeHtml(generatedAt)}</time></span>` : '',
      artifactPath ? `<span>Artifact: ${safeHtml(artifactPath)}</span>` : '',
      scope ? `<span>Scope: ${safeHtml(scope)}</span>` : '',
      `<span>Current artifacts: ${includeCurrent ? 'included' : 'not included'}</span>`,
      `<span>Summary: ${safeHtml(`${scanned} scanned, ${findings} findings, ${missing} missing`)}</span>`,
      findingPatterns.length ? `<span>Finding patterns: ${safeHtml(findingPatterns.join(', '))}</span>` : '',
      missingPaths.length ? `<span>Missing paths: ${safeHtml(missingPaths.join(', '))}</span>` : '',
      scannedSample.length ? `<span>Scanned sample: ${safeHtml(scannedSample.join(', '))}</span>` : '',
      currentArtifactSample.length ? `<span>Current artifact sample: ${safeHtml(currentArtifactSample.join(', '))}</span>` : '',
      actionButtons ? `<span class="operator-packet-action-group" role="group" aria-label="Launch secret scan copy actions">${actionButtons}</span>` : '',
    ].filter(Boolean).join('');
  } catch {
    preview.innerHTML = '<span>Launch secret scan unavailable</span>';
  } finally {
    setOperatorPreviewBusy(button, preview, false);
  }
}

async function loadOperatorReadinessReport(button) {
  const action = button?.closest('.operator-action');
  const preview = action?.querySelector('.operator-readiness-report-preview');
  if (!preview) return;
  if (collapseOperatorPreview(button, preview)) return;
  setOperatorDisclosureState(button, preview, true);
  setOperatorPreviewBusy(button, preview, true);
  preview.innerHTML = '<span>Loading readiness report</span>';
  try {
    const data = await fetch('/api/operator/readiness-report').then(res => res.json());
    const summary = data.summary && typeof data.summary === 'object' ? data.summary : {};
    const failed = Array.isArray(data.failed_checks) ? data.failed_checks.filter(item => item && typeof item === 'object').slice(0, 6) : [];
    const warnings = Array.isArray(data.warning_checks) ? data.warning_checks.filter(item => item && typeof item === 'object').slice(0, 4) : [];
    const generatedAt = typeof data.generated_at === 'string' && data.generated_at.trim() ? data.generated_at.trim() : '';
    const artifactPath = typeof data.path === 'string' && data.path.trim() ? data.path.trim() : '';
    const total = Number(summary.total || 0);
    const passed = Number(summary.passed || 0);
    const failedCount = Number(summary.failed || 0);
    const warningCount = Number(summary.warnings || 0);
    const failedNames = failed.map(item => operatorDisplayCheckName(item)).filter(Boolean);
    const warningNames = warnings.map(item => operatorDisplayCheckName(item)).filter(Boolean);
    const summaryText = total || failedCount || warningCount ? `${passed}/${total} passed, ${failedCount} failed, ${warningCount} warnings` : '';
    const verificationWorkingDirectory = typeof data.verification_working_directory === 'string' && data.verification_working_directory.trim()
      ? data.verification_working_directory.trim()
      : '';
    const verificationCommands = Array.isArray(data.verification_commands) ? data.verification_commands.map(item => String(item || '').trim()).filter(Boolean) : [];
    const verificationCommandBundle = typeof data.verification_command_bundle === 'string' && data.verification_command_bundle.trim()
      ? data.verification_command_bundle.trim()
      : verificationCommands.join('\\n');
    const verificationPreview = verificationCommands.length
      ? `${verificationCommands.slice(0, 3).join(' | ')}${verificationCommands.length > 3 ? ` | +${verificationCommands.length - 3} more` : ''}`
      : '';
    const actionBundle = failed.map((item) => {
      const name = operatorDisplayCheckName(item);
      const level = String(item.level || '').trim();
      const message = String(item.message || '').trim();
      const remediation = String(item.remediation || '').trim();
      const diagnostics = Array.isArray(item.diagnostics) ? item.diagnostics.map(line => String(line || '').trim()).filter(Boolean).slice(0, 4) : [];
      const evidenceSummary = Array.isArray(item.evidence_summary) ? item.evidence_summary.map(line => String(line || '').trim()).filter(Boolean).slice(0, 5) : [];
      const recoveryPacket = String(item.recovery_packet || '').trim();
      const recoveryPacketLabel = String(item.recovery_packet_label || 'Recovery packet').trim();
      const recoveryReuse = item.recovery_packet_reuse && typeof item.recovery_packet_reuse === 'object' ? String(item.recovery_packet_reuse.message || '').trim() : '';
      return [
        `Check: ${name}${level ? ` (${level})` : ''}`,
        message ? `Message: ${message}` : '',
        evidenceSummary.length ? `Evidence:\\n${evidenceSummary.join('\\n')}` : '',
        remediation ? `Action: ${remediation}` : '',
        recoveryPacket ? `Compare packet: ${recoveryPacketLabel} | ${recoveryPacket}${recoveryReuse ? ` | ${recoveryReuse}` : ''}` : '',
        diagnostics.length ? `Diagnostics:\\n${diagnostics.join('\\n')}` : '',
      ].filter(Boolean).join('\\n');
    }).filter(Boolean).join('\\n\\n');
    const actionBundleText = [
      `Readiness report: ${String(data.status || 'unknown')}`,
      generatedAt ? `Generated: ${generatedAt}` : '',
      artifactPath ? `Artifact: ${artifactPath}` : '',
      summaryText ? `Summary: ${summaryText}` : '',
      failedNames.length ? `Failed checks: ${failedNames.join(', ')}` : '',
      actionBundle,
    ].filter(Boolean).join('\\n');
    const failureComparison = failed.map((item) => {
      const name = operatorDisplayCheckName(item);
      const level = String(item.level || '').trim();
      const message = String(item.message || '').trim();
      const evidenceSummary = Array.isArray(item.evidence_summary) ? item.evidence_summary.map(line => String(line || '').trim()).filter(Boolean).slice(0, 5) : [];
      const recoveryPacket = String(item.recovery_packet || '').trim();
      const recoveryPacketLabel = String(item.recovery_packet_label || 'Recovery packet').trim();
      const recoveryReuse = item.recovery_packet_reuse && typeof item.recovery_packet_reuse === 'object' ? String(item.recovery_packet_reuse.message || '').trim() : '';
      return [
        `Check: ${name}${level ? ` (${level})` : ''}`,
        message ? `Message: ${message}` : '',
        evidenceSummary.length ? `Evidence: ${evidenceSummary.join(' | ')}` : '',
        recoveryPacket ? `Compare packet: ${recoveryPacketLabel} | ${recoveryPacket}${recoveryReuse ? ` | ${recoveryReuse}` : ''}` : '',
      ].filter(Boolean).join('\\n');
    }).filter(Boolean).join('\\n\\n');
    const failureComparisonText = [
      `Readiness failure comparison: ${String(data.status || 'unknown')}`,
      generatedAt ? `Generated: ${generatedAt}` : '',
      artifactPath ? `Artifact: ${artifactPath}` : '',
      summaryText ? `Summary: ${summaryText}` : '',
      failureComparison,
    ].filter(Boolean).join('\\n');
    const failedRows = failed.flatMap((item) => {
      const name = String(item.name || 'unknown check').trim();
      const displayName = operatorDisplayCheckName(item);
      const level = String(item.level || '').trim();
      const message = String(item.message || '').trim();
      const remediation = String(item.remediation || '').trim();
      const diagnostics = Array.isArray(item.diagnostics) ? item.diagnostics.map(line => String(line || '').trim()).filter(Boolean).slice(0, 4) : [];
      const evidenceSummary = Array.isArray(item.evidence_summary) ? item.evidence_summary.map(line => String(line || '').trim()).filter(Boolean).slice(0, 5) : [];
      const recoveryPacket = String(item.recovery_packet || '').trim();
      const recoveryPacketLabel = String(item.recovery_packet_label || 'Recovery packet').trim();
      const recoveryReuse = item.recovery_packet_reuse && typeof item.recovery_packet_reuse === 'object' ? String(item.recovery_packet_reuse.message || '').trim() : '';
      return [
        `<span>Blocker: ${safeHtml(displayName)}${level ? safeHtml(` (${level})`) : ''}</span>`,
        message ? `<span>Message: ${safeHtml(message)}</span>` : '',
        evidenceSummary.length ? `<span>Evidence: ${safeHtml(evidenceSummary.join(' | '))}</span>` : '',
        remediation ? `<span>Action: <code>${safeHtml(remediation)}</code></span>` : '',
        recoveryPacket ? `<span>Compare packet: <code>${safeHtml(`${recoveryPacketLabel} | ${recoveryPacket}${recoveryReuse ? ` | ${recoveryReuse}` : ''}`)}</code></span>` : '',
        diagnostics.length ? `<span>Diagnostics: <samp>${safeHtml(diagnostics.join('\\n'))}</samp></span>` : '',
      ].filter(Boolean);
    });
    const readinessActionButtons = [
      actionBundle ? `<button type="button" class="operator-copy-btn" aria-label="Copy readiness action bundle" data-copy-text="${safeHtml(actionBundleText)}" onclick="copyOperatorText(this, this.dataset.copyText || '', 'Readiness actions copied.')">Copy readiness actions</button>` : '',
      failureComparison ? `<button type="button" class="operator-copy-btn" aria-label="Copy readiness failure comparison" data-copy-text="${safeHtml(failureComparisonText)}" onclick="copyOperatorText(this, this.dataset.copyText || '', 'Readiness failure comparison copied.')">Copy failure comparison</button>` : '',
      verificationCommandBundle ? `<button type="button" class="operator-copy-btn" aria-label="Copy readiness verification bundle" data-copy-text="${safeHtml(verificationCommandBundle)}" onclick="copyOperatorText(this, this.dataset.copyText || '', 'Readiness verification copied.')">Copy readiness verification bundle</button>` : '',
    ].filter(Boolean).join('');
    const readinessActionGroup = readinessActionButtons ? `<span class="operator-packet-action-group" role="group" aria-label="Readiness report copy actions">${readinessActionButtons}</span>` : '';
    preview.innerHTML = [
      `<span>Readiness report: ${safeHtml(data.status || 'unknown')}</span>`,
      generatedAt ? `<span>Generated: <time datetime="${safeHtml(generatedAt)}">${safeHtml(generatedAt)}</time></span>` : '',
      artifactPath ? `<span>Artifact: ${safeHtml(artifactPath)}</span>` : '',
      summaryText ? `<span>Summary: ${safeHtml(summaryText)}</span>` : '',
      failedNames.length ? `<span>Failed checks: ${safeHtml(failedNames.join(', '))}</span>` : '',
      warningNames.length ? `<span>Warnings: ${safeHtml(warningNames.join(', '))}</span>` : '',
      verificationWorkingDirectory ? `<span>Verification cwd: ${safeHtml(verificationWorkingDirectory)}</span>` : '',
      readinessActionGroup,
      verificationPreview ? `<span>Verify: ${safeHtml(verificationPreview)}</span>` : '',
      ...failedRows,
    ].filter(Boolean).join('');
  } catch {
    preview.innerHTML = '<span>Readiness report unavailable</span>';
  } finally {
    setOperatorPreviewBusy(button, preview, false);
  }
}

function loadOperatorArtifactImage(button) {
  const action = button?.closest('.operator-action');
  const preview = action?.querySelector('.operator-packet-preview');
  if (!preview) return;
  if (collapseOperatorPreview(button, preview)) return;
  const imagePath = String(button?.dataset?.imagePath || '').trim();
  const imageAlt = String(button?.dataset?.imageAlt || 'Operator artifact image').trim();
  setOperatorDisclosureState(button, preview, true);
  if (!imagePath) {
    preview.innerHTML = '<span>Screenshot unavailable</span>';
    return;
  }
  const imageSrc = `/api/operator/artifact-image?path=${encodeURIComponent(imagePath)}`;
  preview.innerHTML = [
    `<span>Screenshot: ${safeHtml(imagePath)}</span>`,
    `<img class="operator-artifact-image-preview" src="${safeHtml(imageSrc)}" alt="${safeHtml(imageAlt)}" width="960" height="540" loading="eager" decoding="async">`,
    `<span class="operator-image-error" hidden></span>`,
  ].join('');
  const image = preview.querySelector('img');
  const error = preview.querySelector('.operator-image-error');
  if (image && error) {
    image.addEventListener('error', () => {
      error.textContent = 'Screenshot unavailable';
      error.hidden = false;
    }, { once: true });
  }
}

function operatorArtifactFallbackActions(artifacts) {
  const readinessReport = String(artifacts.readiness || '').trim();
  const readinessRefresh = String(artifacts.readiness_refresh_command || '').trim();
  const launchSecretScan = String(artifacts.launch_secret_scan || '').trim();
  const launchSecretScanRefresh = String(artifacts.launch_secret_scan_refresh_command || '').trim();
  const credentialInputStatus = String(artifacts.credential_input_status || '').trim();
  const providerPacket = String(artifacts.provider_auth_recovery_packet || '').trim();
  const dashboardBrowser = String(artifacts.browser || '').trim();
  const dashboardBrowserScreenshot = String(artifacts.browser_screenshot || '').trim();
  const tapFixtureBrowser = String(artifacts.tap_fixture_browser || '').trim();
  const tapFixtureScreenshot = String(artifacts.tap_fixture_browser_screenshot || '').trim();
  const tapFixtureRefresh = String(artifacts.tap_fixture_browser_refresh_command || '').trim();
  const schedulerArtifact = String(artifacts.scheduler || '').trim();
  const workspaceSmoke = String(artifacts.workspace_smoke || '').trim();
  return [
    readinessReport ? { key: 'readiness_report', label: 'Readiness report', value: readinessReport, copy_label: 'Copy readiness report path', view: { kind: 'readiness_report', label: 'View readiness report', hide_label: 'Hide readiness report', view_text: 'View report', hide_text: 'Hide report', controls: 'operator-readiness-report-preview', preview_class: 'operator-readiness-report-preview' } } : null,
    readinessRefresh ? { key: 'readiness_refresh', label: 'Readiness refresh', value: readinessRefresh, copy_label: 'Copy readiness refresh command' } : null,
    launchSecretScan ? { key: 'launch_secret_scan', label: 'Launch secret scan', value: launchSecretScan, copy_label: 'Copy launch secret scan path', view: { kind: 'launch_secret_scan', label: 'View launch secret scan', hide_label: 'Hide launch secret scan', view_text: 'View scan', hide_text: 'Hide scan', controls: 'operator-launch-secret-scan-preview', preview_class: 'operator-launch-secret-scan-preview' } } : null,
    launchSecretScanRefresh ? { key: 'launch_secret_scan_refresh', label: 'Launch secret scan refresh', value: launchSecretScanRefresh, copy_label: 'Copy launch secret scan refresh command' } : null,
    credentialInputStatus ? { key: 'credential_input_status', label: 'Credential input status', value: credentialInputStatus, copy_label: 'Copy credential input status path' } : null,
    providerPacket ? { key: 'provider_auth_recovery_packet', label: 'Provider recovery packet', value: providerPacket, copy_label: 'Copy provider recovery packet path', view: { kind: 'recovery_packet', label: 'View provider recovery packet', hide_label: 'Hide provider recovery packet', view_text: 'View provider packet', hide_text: 'Hide provider packet', controls: 'operator-provider-recovery-packet-preview', preview_class: 'operator-provider-recovery-packet-preview' } } : null,
    dashboardBrowser ? { key: 'dashboard_browser_report', label: 'Dashboard browser report', value: dashboardBrowser, copy_label: 'Copy dashboard browser report path' } : null,
    dashboardBrowserScreenshot ? { key: 'dashboard_browser_screenshot', label: 'Dashboard browser screenshot', value: dashboardBrowserScreenshot, copy_label: 'Copy dashboard browser screenshot path', view: { kind: 'artifact_image', label: 'View dashboard browser screenshot', hide_label: 'Hide dashboard browser screenshot', view_text: 'View screenshot', hide_text: 'Hide screenshot', controls: 'operator-dashboard-browser-screenshot-preview', preview_class: 'operator-dashboard-browser-screenshot-preview', image_path: dashboardBrowserScreenshot, image_alt: 'Dashboard browser smoke screenshot' } } : null,
    tapFixtureBrowser ? { key: 'tap_fixture_report', label: 'TAP fixture report', value: tapFixtureBrowser, copy_label: 'Copy TAP fixture report path' } : null,
    tapFixtureScreenshot ? { key: 'tap_fixture_screenshot', label: 'TAP fixture screenshot', value: tapFixtureScreenshot, copy_label: 'Copy TAP fixture screenshot path', view: { kind: 'artifact_image', label: 'View TAP fixture screenshot', hide_label: 'Hide TAP fixture screenshot', view_text: 'View screenshot', hide_text: 'Hide screenshot', controls: 'operator-tap-fixture-screenshot-preview', preview_class: 'operator-tap-fixture-screenshot-preview', image_path: tapFixtureScreenshot, image_alt: 'TAP fixture browser smoke screenshot' } } : null,
    tapFixtureRefresh ? { key: 'tap_fixture_refresh', label: 'TAP fixture refresh', value: tapFixtureRefresh, copy_label: 'Copy TAP fixture refresh command' } : null,
    schedulerArtifact ? { key: 'scheduler_artifact', label: 'Scheduler artifact', value: schedulerArtifact, copy_label: 'Copy scheduler artifact path' } : null,
    workspaceSmoke ? { key: 'workspace_smoke', label: 'Workspace smoke', value: workspaceSmoke, copy_label: 'Copy workspace smoke path', view: { kind: 'workspace_smoke', label: 'View workspace smoke', hide_label: 'Hide workspace smoke', view_text: 'View workspace', hide_text: 'Hide workspace', controls: 'operator-workspace-smoke-preview', preview_class: 'operator-workspace-smoke-preview' } } : null,
  ].filter(Boolean);
}

function operatorDefaultDisclosureText(kind, expanded) {
  if (kind === 'readiness_report') return expanded ? 'Hide report' : 'View report';
  if (kind === 'workspace_smoke') return expanded ? 'Hide workspace' : 'View workspace';
  if (kind === 'launch_secret_scan') return expanded ? 'Hide scan' : 'View scan';
  if (kind === 'artifact_image') return expanded ? 'Hide screenshot' : 'View screenshot';
  if (kind === 'recovery_packet') return expanded ? 'Hide packet' : 'View packet';
  return '';
}

function operatorArtifactViewButton(action) {
  const view = action.view && typeof action.view === 'object' ? action.view : null;
  if (!view) return '';
  const kind = String(view.kind || '').trim();
  const label = String(view.label || 'View artifact').trim();
  const hideLabel = String(view.hide_label || label.replace(/^View/, 'Hide')).trim();
  const defaultViewText = operatorDefaultDisclosureText(kind, false) || label;
  const defaultHideText = operatorDefaultDisclosureText(kind, true) || hideLabel;
  const viewText = String(view.view_text || defaultViewText).trim();
  const hideText = String(view.hide_text || defaultHideText).trim();
  const controls = String(view.controls || '').trim();
  if (!controls) return '';
  if (kind === 'readiness_report') {
    return `<button type="button" class="operator-view-btn" aria-label="${safeHtml(label)}" data-view-label="${safeHtml(label)}" data-hide-label="${safeHtml(hideLabel)}" data-view-text="${safeHtml(viewText)}" data-hide-text="${safeHtml(hideText)}" aria-expanded="false" aria-busy="false" aria-controls="${safeHtml(controls)}" onclick="loadOperatorReadinessReport(this)">${safeHtml(viewText)}</button>`;
  }
  if (kind === 'workspace_smoke') {
    const artifactPath = String(action.value || '').trim();
    return `<button type="button" class="operator-view-btn" aria-label="${safeHtml(label)}" data-view-label="${safeHtml(label)}" data-hide-label="${safeHtml(hideLabel)}" data-view-text="${safeHtml(viewText)}" data-hide-text="${safeHtml(hideText)}" aria-expanded="false" aria-busy="false" aria-controls="${safeHtml(controls)}" data-artifact-path="${safeHtml(artifactPath)}" onclick="loadOperatorWorkspaceSmoke(this)">${safeHtml(viewText)}</button>`;
  }
  if (kind === 'launch_secret_scan') {
    const artifactPath = String(action.value || '').trim();
    return `<button type="button" class="operator-view-btn" aria-label="${safeHtml(label)}" data-view-label="${safeHtml(label)}" data-hide-label="${safeHtml(hideLabel)}" data-view-text="${safeHtml(viewText)}" data-hide-text="${safeHtml(hideText)}" aria-expanded="false" aria-busy="false" aria-controls="${safeHtml(controls)}" data-artifact-path="${safeHtml(artifactPath)}" onclick="loadOperatorLaunchSecretScan(this)">${safeHtml(viewText)}</button>`;
  }
  if (kind === 'recovery_packet') {
    return `<button type="button" class="operator-view-btn" aria-label="${safeHtml(label)}" data-view-label="${safeHtml(label)}" data-hide-label="${safeHtml(hideLabel)}" data-view-text="${safeHtml(viewText)}" data-hide-text="${safeHtml(hideText)}" aria-expanded="false" aria-busy="false" aria-controls="${safeHtml(controls)}" onclick="loadOperatorRecoveryPacket(this)">${safeHtml(viewText)}</button>`;
  }
  if (kind === 'artifact_image') {
    const imagePath = String(view.image_path || action.value || '').trim();
    const imageAlt = String(view.image_alt || 'Operator artifact image').trim();
    return `<button type="button" class="operator-view-btn" aria-label="${safeHtml(label)}" data-view-label="${safeHtml(label)}" data-hide-label="${safeHtml(hideLabel)}" data-view-text="${safeHtml(viewText)}" data-hide-text="${safeHtml(hideText)}" aria-expanded="false" aria-busy="false" aria-controls="${safeHtml(controls)}" data-image-path="${safeHtml(imagePath)}" data-image-alt="${safeHtml(imageAlt)}" onclick="loadOperatorArtifactImage(this)">${safeHtml(viewText)}</button>`;
  }
  return '';
}

function operatorArtifactCopyText(copyLabel) {
  const normalized = String(copyLabel || '').trim().toLowerCase();
  if (normalized.endsWith(' command')) return 'Copy command';
  if (normalized.endsWith(' path')) return 'Copy path';
  return 'Copy';
}

function operatorArtifactNotes(action) {
  const notes = Array.isArray(action.notes) ? action.notes : [];
  return notes.map(note => {
    const label = String(note?.label || '').trim();
    if (!label) return '';
    const state = String(note?.state || 'unknown').trim().toLowerCase().replace(/[^a-z0-9_-]/g, '');
    const stateClass = state ? ` operator-action-note-${safeHtml(state)}` : '';
    return `<span class="operator-action-note${stateClass}">${safeHtml(label)}</span>`;
  }).filter(Boolean).join('');
}

function renderOperatorArtifactAction(action) {
  if (!action || typeof action !== 'object') return '';
  const label = String(action.label || '').trim();
  const value = String(action.value || '').trim();
  if (!label || !value) return '';
  const key = String(action.key || label).trim();
  const copyLabel = String(action.copy_label || `Copy ${label} path`).trim();
  const copyText = operatorArtifactCopyText(copyLabel);
  const notes = operatorArtifactNotes(action);
  const view = action.view && typeof action.view === 'object' ? action.view : null;
  const viewButton = operatorArtifactViewButton(action);
  const copyButton = `<button type="button" class="operator-copy-btn" aria-label="${safeHtml(copyLabel)}" onclick="copyOperatorAction(this)">${safeHtml(copyText)}</button>`;
  const controls = view ? String(view.controls || '').trim() : '';
  const previewClass = view ? String(view.preview_class || '').trim() : '';
  const preview = controls ? `<div id="${safeHtml(controls)}" class="operator-packet-preview ${safeHtml(previewClass)}" aria-live="polite" aria-busy="false" hidden></div>` : '';
  const actionTitle = `<span class="operator-action-title"><span class="operator-action-label">${safeHtml(label)}</span>${notes}</span>`;
  const actionGroupLabel = `${label} artifact actions`;
  const buttons = `<span class="operator-action-button-group" role="group" aria-label="${safeHtml(actionGroupLabel)}" data-artifact-action-group="true">${viewButton ? `${viewButton} ` : ''}${copyButton}</span>`;
  return `<div class="operator-action" data-artifact-key="${safeHtml(key)}"><div class="operator-action-head">${actionTitle}${buttons}</div><code>${safeHtml(value)}</code>${preview}</div>`;
}

async function loadOperatorReadiness() {
  const data = await fetch('/api/operator/readiness').then(res => res.json()).catch(() => ({ cards: [], blockers: [{ name: 'operator_readiness', message: 'Operator readiness evidence is unavailable.', level: 'FAIL' }], warnings: [] }));
  const cards = Array.isArray(data.cards) ? data.cards : [];
  document.getElementById('operator-readiness').innerHTML = cards.length ? cards.map(card => `<div class="operator-card"><div class="label">${safeHtml(card.label || 'Metric')}</div><div class="operator-value">${safeHtml(card.value ?? '-')}</div>${card.detail ? `<div class="operator-card-detail">${safeHtml(card.detail)}</div>` : ''}<span class="operator-state ${operatorStateClass(card.state)}">${safeHtml(card.state || 'unknown')}</span></div>`).join('') : '<div class="operator-card"><div class="operator-item-title">No readiness evidence</div><div class="operator-item-body">Run the readiness check to populate this panel.</div></div>';
  const artifacts = data.artifacts && typeof data.artifacts === 'object' ? data.artifacts : {};
  const artifactActions = Array.isArray(data.artifact_actions) ? data.artifact_actions : operatorArtifactFallbackActions(artifacts);
  document.getElementById('operator-artifacts').innerHTML = artifactActions.map(renderOperatorArtifactAction).filter(Boolean).join('');
  const blockers = Array.isArray(data.blockers) ? data.blockers : [];
  const warnings = Array.isArray(data.warnings) ? data.warnings : [];
  const items = [...blockers.map(item => ({ ...item, kind: 'Blocker' })), ...warnings.map(item => ({ ...item, kind: 'Warning' }))];
  document.getElementById('operator-blockers').innerHTML = items.length ? items.map((item, index) => {
    const itemIdSuffix = safeId(`${item.kind || 'item'}-${item.name || index}`, 'operator-item-' + index);
    const itemTitleId = `operator-blocker-title-${itemIdSuffix}`;
    const itemDisplayName = operatorDisplayCheckName(item);
    const labelledBy = (buttonId) => `id="${safeHtml(buttonId)}" aria-labelledby="${safeHtml(buttonId)} ${safeHtml(itemTitleId)}"`;
    const diagnostics = Array.isArray(item.diagnostics) ? item.diagnostics.filter(Boolean).slice(0, 6) : [];
    const diagnosticHtml = diagnostics.length ? `<div class="operator-diagnostics">${diagnostics.map(line => `<code>${safeHtml(line)}</code>`).join('')}</div>` : '';
    const evidenceSummary = Array.isArray(item.evidence_summary) ? item.evidence_summary.map(line => String(line || '').trim()).filter(Boolean).slice(0, 5) : [];
    const evidenceHtml = evidenceSummary.length ? `<div class="operator-evidence-summary">${evidenceSummary.map(line => `<span>${safeHtml(line)}</span>`).join('')}</div>` : '';
    const describedBy = `aria-describedby="${safeHtml(itemTitleId)}"`;
    const remediationButtonId = `operator-remediation-copy-${itemIdSuffix}`;
    const packetViewButtonId = `operator-recovery-packet-view-${itemIdSuffix}`;
    const packetBundleButtonId = `operator-recovery-bundle-copy-${itemIdSuffix}`;
    const packetVerifyButtonId = `operator-recovery-verify-copy-${itemIdSuffix}`;
    const packetSuccessButtonId = `operator-recovery-success-copy-${itemIdSuffix}`;
    const packetSchedulerPauseButtonId = `operator-recovery-scheduler-pause-copy-${itemIdSuffix}`;
    const packetCredentialUpdateButtonId = `operator-recovery-credential-update-copy-${itemIdSuffix}`;
    const packetSchedulerResumeButtonId = `operator-recovery-scheduler-resume-copy-${itemIdSuffix}`;
    const packetPathButtonId = `operator-recovery-path-copy-${itemIdSuffix}`;
    const remediationHtml = item.remediation ? `<div class="operator-action"><div class="operator-action-head"><span class="operator-action-label">Action</span><button type="button" class="operator-copy-btn" aria-label="Copy remediation action" ${labelledBy(remediationButtonId)} ${describedBy} onclick="copyOperatorAction(this)">Copy remediation action</button></div><code>${safeHtml(item.remediation)}</code></div>` : '';
    const packetPreviewId = item.recovery_packet ? `operator-recovery-packet-preview-${safeId(item.name || index, 'packet-' + index)}` : '';
    const packetReuse = item.recovery_packet_reuse && typeof item.recovery_packet_reuse === 'object' ? item.recovery_packet_reuse : null;
    const packetReuseLabel = packetReuse ? String(packetReuse.message || (packetReuse.first_blocker ? `Same packet as ${packetReuse.first_blocker}` : '') || '').trim() : '';
    const packetReuseHtml = packetReuseLabel ? `<span class="operator-action-note">${safeHtml(packetReuseLabel)}</span>` : '';
    const recoveryTitleHtml = `<span class="operator-action-title"><span class="operator-action-label">Recovery packet</span>${packetReuseHtml ? ` ${packetReuseHtml}` : ''}</span>`;
    const recoveryPacketHtml = item.recovery_packet ? `<div class="operator-action"><div class="operator-action-head">${recoveryTitleHtml}<span role="group" aria-label="Recovery row copy actions" data-recovery-row-actions="true"><button type="button" class="operator-view-btn" aria-label="View recovery packet" ${labelledBy(packetViewButtonId)} data-view-label="View recovery packet" data-hide-label="Hide recovery packet" data-view-text="View recovery packet" data-hide-text="Hide recovery packet" aria-expanded="false" aria-busy="false" aria-controls="${safeHtml(packetPreviewId)}" ${describedBy} onclick="loadOperatorRecoveryPacket(this)">View recovery packet</button> <button type="button" class="operator-copy-btn" aria-label="Copy scheduler pause commands from blocker row" ${labelledBy(packetSchedulerPauseButtonId)} ${describedBy} onclick="copyOperatorSchedulerPauseCommands(this)">Copy scheduler pause</button> <button type="button" class="operator-copy-btn" aria-label="Copy credential update commands from blocker row" ${labelledBy(packetCredentialUpdateButtonId)} ${describedBy} onclick="copyOperatorCredentialUpdateCommands(this)">Copy credential update</button> <button type="button" class="operator-copy-btn" aria-label="Copy recovery bundle" ${labelledBy(packetBundleButtonId)} ${describedBy} onclick="copyOperatorRecoveryBundle(this)">Copy recovery bundle</button> <button type="button" class="operator-copy-btn" aria-label="Copy recovery verification bundle" ${labelledBy(packetVerifyButtonId)} ${describedBy} onclick="copyOperatorRecoveryVerify(this)">Copy recovery verification bundle</button> <button type="button" class="operator-copy-btn" aria-label="Copy launch success criteria" ${labelledBy(packetSuccessButtonId)} ${describedBy} onclick="copyOperatorRecoverySuccess(this)">Copy launch criteria</button> <button type="button" class="operator-copy-btn" aria-label="Copy scheduler resume commands from blocker row" ${labelledBy(packetSchedulerResumeButtonId)} ${describedBy} onclick="copyOperatorSchedulerResumeCommands(this)">Copy scheduler resume</button> <button type="button" class="operator-copy-btn" aria-label="Copy recovery packet path" ${labelledBy(packetPathButtonId)} ${describedBy} onclick="copyOperatorAction(this)">Copy packet path</button></span></div><code>${safeHtml(item.recovery_packet)}</code><div id="${safeHtml(packetPreviewId)}" class="operator-packet-preview" aria-live="polite" aria-busy="false" hidden></div></div>` : '';
    return `<div class="operator-item"><div id="${safeHtml(itemTitleId)}" class="operator-item-title">${safeHtml(item.kind)}: ${safeHtml(itemDisplayName)}</div><div class="operator-item-body">${safeHtml(item.message || '-')}</div>${evidenceHtml}${diagnosticHtml}${remediationHtml}${recoveryPacketHtml}</div>`;
  }).join('') : '<div class="operator-item"><div class="operator-item-title">No posting blockers</div><div class="operator-item-body">Current smoke, browser, scheduler, hygiene, and docs evidence is green.</div></div>';
}

function normalizeTapPreset(value) { return String(value || '').trim().toLowerCase(); }
function getTapTargetCountry() { return normalizeTapPreset(document.getElementById('tap-target-country')?.value); }
function getTapAlertLifecycle() { return normalizeTapPreset(document.getElementById('tap-alert-lifecycle')?.value); }
function getTapAlertLimit() { const n = Number(document.getElementById('tap-alert-limit')?.value || 6); return Number.isFinite(n) && n > 0 ? n : 6; }
function buildTapQuery(params) { const query = new URLSearchParams(); Object.entries(params || {}).forEach(([key, value]) => { if (value !== undefined && value !== null && value !== '') query.set(key, String(value)); }); return query.toString(); }
function readTapPresets() { try { const raw = localStorage.getItem(TAP_PRESET_STORAGE_KEY); const parsed = raw ? JSON.parse(raw) : ['', 'korea', 'united-states', 'japan']; return Array.isArray(parsed) ? parsed : ['', 'korea', 'united-states', 'japan']; } catch { return ['', 'korea', 'united-states', 'japan']; } }
function writeTapPresets(values) { localStorage.setItem(TAP_PRESET_STORAGE_KEY, JSON.stringify([...new Set(['', ...values.map(normalizeTapPreset).filter(Boolean)])].slice(0, 8))); }
function renderTapPresetStrip() { const active = getTapTargetCountry(); document.getElementById('tap-preset-strip').innerHTML = readTapPresets().map(value => { const label = value ? value.toUpperCase() : 'ALL'; return `<button type="button" class="tap-preset-btn ${value === active ? 'tap-preset-btn-active' : ''}" aria-pressed="${value === active ? 'true' : 'false'}" aria-label="Apply TAP target market preset: ${safeHtml(label)}" onclick="applyTapPreset('${safeHtml(value)}')">${safeHtml(label)}</button>`; }).join(''); }
function applyTapPreset(value = '') { document.getElementById('tap-target-country').value = normalizeTapPreset(value); renderTapPresetStrip(); syncTapOpsView(); }
function handleTapTargetMarketKey(event) { if (event.key !== 'Enter') return; event.preventDefault(); renderTapPresetStrip(); syncTapOpsView(); }
async function saveCurrentTapPreset() {
  const current = getTapTargetCountry();
  if (!current) return toast('Enter a market before saving a preset.', 'error');
  writeTapPresets([current, ...readTapPresets()]);
  renderTapPresetStrip();
  document.getElementById('tap-alert-status').textContent = `Applying ${current.toUpperCase()} preset...`;
  try {
    await syncTapOpsView();
    toast(`Saved and applied preset for ${current.toUpperCase()}.`);
  } catch {
    toast(`Saved preset for ${current.toUpperCase()}, but target refresh failed.`, 'error');
  }
}
async function resetTapPresets() {
  writeTapPresets(['korea', 'united-states', 'japan']);
  const target = document.getElementById('tap-target-country');
  if (target) target.value = '';
  renderTapPresetStrip();
  document.getElementById('tap-alert-status').textContent = 'Resetting TAP presets...';
  try {
    await syncTapOpsView();
    toast('Preset markets reset and filter cleared.');
  } catch {
    toast('Preset markets reset, but queue refresh failed.', 'error');
  }
}

function formatTapCount(value) {
  const number = Number(value || 0);
  return Number.isFinite(number) ? String(Math.round(number)) : '0';
}

function formatTapMoney(value) {
  const number = Number(value || 0);
  if (!Number.isFinite(number) || number <= 0) return '$0';
  return `$${number.toFixed(number % 1 === 0 ? 0 : 2)}`;
}

function formatTapRate(value) {
  const number = Number(value || 0);
  if (!Number.isFinite(number) || number <= 0) return '0%';
  const percent = number <= 1 ? number * 100 : number;
  return `${percent.toFixed(percent >= 10 ? 0 : 1)}%`;
}

function renderTapDealMetric(label, value) {
  return `<div class="tap-deal-metric"><div class="tap-deal-metric-label">${safeHtml(label)}</div><div class="tap-deal-metric-value">${safeHtml(value)}</div></div>`;
}

function renderTapDealOpsSummary(funnelData, checkoutData) {
  const funnelTotals = funnelData && typeof funnelData === 'object' ? (funnelData.totals || {}) : {};
  const checkoutTotals = checkoutData && typeof checkoutData === 'object' ? (checkoutData.totals || {}) : {};
  const windowDays = Number(funnelData?.window_days || checkoutData?.window_days || 30);
  const metrics = [
    ['Views', formatTapCount(funnelTotals.views)],
    ['Clicks', formatTapCount(funnelTotals.clicks)],
    ['Checkouts', formatTapCount(funnelTotals.checkout_opens)],
    ['Purchases', formatTapCount(funnelTotals.purchases || checkoutTotals.paid)],
    ['Revenue', formatTapMoney(funnelTotals.revenue || checkoutTotals.captured_revenue)],
    ['Checkout completion', formatTapRate(checkoutTotals.completion_rate)],
  ];
  return `<div id="tap-deal-ops-summary" class="tap-deal-card tap-deal-card-wide" aria-live="polite"><div class="tap-title">${safeHtml(windowDays)}d Deal Room ops</div><div class="tap-copy">Funnel and checkout counters stay visible even when no offer bundle is ready.</div><div class="tap-deal-ops-grid">${metrics.map(([label, value]) => renderTapDealMetric(label, value)).join('')}</div></div>`;
}

function buildTapDealRoomEventQuery(offer, eventType) {
  const query = new URLSearchParams();
  const fields = {
    keyword: offer.keyword || offer.teaser_headline || '',
    event_type: eventType,
    snapshot_id: offer.snapshot_id || '',
    target_country: offer.target_country || getTapTargetCountry(),
    audience_segment: offer.audience_segment || 'creator',
    package_tier: offer.package_tier || 'premium_alert_bundle',
    offer_tier: offer.tier || offer.offer_tier || 'teaser',
    price_anchor: offer.price_anchor || '',
    checkout_handle: offer.checkout_handle || '',
  };
  Object.entries(fields).forEach(([key, value]) => { if (value !== undefined && value !== null && value !== '') query.set(key, String(value)); });
  return query.toString();
}

function tapDealRoomOfferKeyword(offer) {
  return String(offer.keyword || offer.teaser_headline || '').trim();
}

function buildTapDealRoomCheckoutPayload(offer) {
  const keyword = tapDealRoomOfferKeyword(offer);
  return {
    keyword,
    snapshot_id: offer.snapshot_id || '',
    target_country: offer.target_country || getTapTargetCountry(),
    audience_segment: offer.audience_segment || 'creator',
    package_tier: offer.package_tier || 'premium_alert_bundle',
    offer_tier: offer.tier || offer.offer_tier || 'premium',
    price_anchor: offer.price_anchor || '',
    quoted_price_value: offer.price_value ?? '',
    premium_title: offer.premium_title || offer.teaser_headline || keyword,
    teaser_body: offer.teaser_body || '',
    checkout_handle: offer.checkout_handle || '',
    currency: offer.currency || 'usd',
    actor_id: 'dashboard',
    pricing_variant: offer.pricing_variant || '',
    pricing_context: offer.pricing_context && typeof offer.pricing_context === 'object' ? offer.pricing_context : {},
  };
}

function renderTapDealOfferActions(offer, index) {
  const checkoutHandle = String(offer.checkout_handle || '').trim();
  const offerName = String(offer.teaser_headline || offer.keyword || offer.premium_title || 'Deal room offer').trim();
  const safeOfferName = safeHtml(offerName);
  const actionGroupLabel = `${offerName} offer actions`;
  const checkoutLabel = offer.cta_label || 'Open checkout';
  const checkoutButton = checkoutHandle
    ? `<button type="button" class="tap-btn tap-checkout-btn" aria-label="${safeHtml(`${checkoutLabel}: ${offerName}`)}" data-tap-checkout-index="${safeHtml(index)}" onclick="openTapOfferCheckout(${index}, this)">${safeHtml(checkoutLabel)}</button>`
    : '';
  return `<div class="tap-actions" role="group" aria-label="${safeHtml(actionGroupLabel)}" data-tap-offer-actions="true" data-offer-name="${safeOfferName}"><button type="button" class="tap-btn tap-btn-ghost" aria-label="${safeHtml(`Track offer click: ${offerName}`)}" onclick="trackTapOfferClick(${index})">Track click</button>${checkoutButton}</div>`;
}

async function loadTapBoard() {
  const country = getTapTargetCountry();
  const data = await fetchPanel(`/api/tap/opportunities?${buildTapQuery({ limit: 6, teaser_count: 2, target_country: country })}`, 'TAP opportunities');
  const items = Array.isArray(data.items) ? data.items : [];
  document.getElementById('tap-board').innerHTML = items.length ? items.map(item => {
    const notes = Array.isArray(item.execution_notes) ? item.execution_notes.filter(Boolean).slice(0, 2) : [];
    const noteHtml = notes.length ? `<div class="tap-notes">${notes.map(note => `- ${safeHtml(note)}`).join('<br>')}</div>` : '';
    return `<div class="tap-card"><div class="tap-title">${safeHtml(item.keyword || 'Untitled signal')}</div><div class="tap-meta"><span class="tap-chip">score ${safeHtml(item.viral_score ?? '-')}</span><span class="tap-chip">priority ${safeHtml(item.priority ?? '-')}</span><span class="tap-badge">${safeHtml(item.paywall_tier || 'Premium')}</span></div><div class="tap-copy">${safeHtml(item.public_teaser || item.recommended_angle || 'No teaser available yet.')}</div>${noteHtml}</div>`;
  }).join('') : `<div class="tap-card"><div class="tap-title">No live arbitrage slots${country ? ` for ${safeHtml(country.toUpperCase())}` : ''}</div><div class="tap-copy">The board will refill when a market gap opens.</div></div>`;
}

async function loadTapDealRoom() {
  const country = getTapTargetCountry();
  const [data, funnelData, checkoutData] = await Promise.all([
    fetchPanel(`/api/tap/deal-room?${buildTapQuery({ limit: 4, teaser_count: 2, target_country: country, audience_segment: 'creator', include_checkout: 'true' })}`, 'TAP deal room').catch(() => ({ offers: [] })),
    fetchPanel(`/api/tap/deal-room/funnel?${buildTapQuery({ days: 30, target_country: country, audience_segment: 'creator', package_tier: 'premium_alert_bundle' })}`, 'TAP deal-room funnel').catch(() => ({ totals: {} })),
    fetchPanel(`/api/tap/deal-room/checkouts?${buildTapQuery({ days: 30, target_country: country, audience_segment: 'creator', package_tier: 'premium_alert_bundle' })}`, 'TAP deal-room checkouts').catch(() => ({ totals: {} })),
  ]);
  const offers = Array.isArray(data.offers) ? data.offers : [];
  currentTapDealRoomOffers = offers;
  const offerCards = offers.length ? offers.map((offer, index) => `<div class="tap-deal-card tap-deal-offer-card"><div class="tap-title">${safeHtml(offer.teaser_headline || offer.keyword || 'Untitled bundle')}</div><div class="tap-price">${safeHtml(offer.price_anchor || '$0')}</div><div class="tap-copy">${safeHtml(offer.teaser_body || offer.premium_title || 'Premium package pending.')}</div>${renderTapDealOfferActions(offer, index)}</div>`).join('') : `<div class="tap-deal-card tap-deal-empty-card"><div class="tap-title">No monetizable bundle ready${country ? ` for ${safeHtml(country.toUpperCase())}` : ''}</div><div class="tap-copy">When the next arbitrage gap opens, this room will package teaser and premium lanes automatically.</div></div>`;
  document.getElementById('tap-deal-room').innerHTML = `${renderTapDealOpsSummary(funnelData, checkoutData)}${offerCards}`;
}

async function trackTapOfferClick(index) {
  const offer = currentTapDealRoomOffers[index] || {};
  const keyword = tapDealRoomOfferKeyword(offer);
  if (!keyword) {
    toast('Offer click could not be tracked: missing keyword.', 'error');
    return;
  }
  try {
    const data = await fetchPanel(`/api/tap/deal-room/events?${buildTapDealRoomEventQuery(offer, 'click')}`, 'TAP deal-room events', { method: 'POST' });
    if (!data.ok) throw new Error(data.error || 'tracking failed');
    toast(`Offer click tracked for ${keyword}.`);
    await loadTapDealRoom();
  } catch {
    toast(`Offer click tracking failed for ${keyword}.`, 'error');
  }
}

async function openTapOfferCheckout(index, button) {
  const offer = currentTapDealRoomOffers[index] || {};
  const keyword = tapDealRoomOfferKeyword(offer);
  const checkoutHandle = String(offer.checkout_handle || '').trim();
  if (!keyword || !checkoutHandle) {
    toast('Checkout could not be opened: missing offer checkout details.', 'error');
    return;
  }
  const originalText = button?.innerText || '';
  if (button) {
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    button.innerText = 'Opening...';
  }
  try {
    const data = await fetchPanel('/api/tap/deal-room/checkout', 'TAP deal-room checkout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(buildTapDealRoomCheckoutPayload(offer)),
    });
    if (!data.ok || !data.url) throw new Error(data.error || 'checkout session unavailable');
    const opened = window.open(data.url, '_blank', 'noopener,noreferrer');
    if (!opened) window.location.assign(data.url);
    toast(`Checkout opened for ${keyword}.`);
    await loadTapDealRoom();
  } catch (error) {
    const message = error instanceof Error ? error.message : 'checkout unavailable';
    toast(`Checkout unavailable for ${keyword}: ${message}.`, 'error');
  } finally {
    if (button) {
      button.disabled = false;
      button.setAttribute('aria-busy', 'false');
      button.innerText = originalText || offer.cta_label || 'Open checkout';
    }
  }
}

function renderTapSummary(counts, channels) {
  document.getElementById('tap-alert-summary').innerHTML = [
    ['Queued', counts.queued || 0], ['Dispatched', counts.dispatched || 0], ['Failed', counts.failed || 0], ['Channels', channels],
  ].map(([label, value]) => `<div class="tap-summary-card"><div class="tap-summary-label">${label}</div><div class="tap-summary-value">${safeHtml(value)}</div></div>`).join('');
}

function renderOutcomes(items) {
  const outcomes = Array.isArray(items) ? items : [];
  document.getElementById('tap-outcome-list').innerHTML = outcomes.length ? outcomes.slice(0, 4).map(item => `<div class="tap-outcome-card"><div class="tap-alert-title">${safeHtml(item.keyword || 'Untitled outcome')}</div><div class="tap-alert-body">${safeHtml(item.alert_message || 'Recent dispatch outcome')}</div><div class="tap-meta"><span class="tap-chip">${safeHtml(item.lifecycle_status || 'unknown')}</span><span class="tap-chip">score ${safeHtml(item.viral_score ?? '-')}</span></div></div>`).join('') : '<div class="tap-outcome-card"><div class="tap-alert-title">No dispatch attempts yet</div><div class="tap-alert-body">Dispatch outcomes will appear here after the first delivery attempt.</div></div>';
}

function tapAlertLifecycleCopy(lifecycle) {
  const value = normalizeTapPreset(lifecycle);
  return value ? `${value} alert(s)` : 'alert(s)';
}

function tapAlertEmptyTitle(lifecycle, country) {
  const value = normalizeTapPreset(lifecycle);
  const stateCopy = value ? `${value} alerts` : 'alerts';
  return `No ${stateCopy}${country ? ` for ${country.toUpperCase()}` : ''}`;
}

async function loadTapAlerts() {
  const country = getTapTargetCountry();
  const lifecycle = getTapAlertLifecycle();
  const limit = getTapAlertLimit();
  const selectedAlertLabel = lifecycle ? `TAP alerts ${lifecycle}` : 'TAP alerts selected all states';
  const [countsData, queueData, dispatchedData, failedData] = await Promise.all([
    fetchPanel(`/api/tap/alerts?${buildTapQuery({ limit: 50, lifecycle_status: '', target_country: country })}`, 'TAP alerts count summary'),
    fetchPanel(`/api/tap/alerts?${buildTapQuery({ limit, lifecycle_status: lifecycle, target_country: country })}`, selectedAlertLabel),
    fetchPanel(`/api/tap/alerts?${buildTapQuery({ limit: 3, lifecycle_status: 'dispatched', target_country: country })}`, 'TAP alerts dispatched outcomes'),
    fetchPanel(`/api/tap/alerts?${buildTapQuery({ limit: 3, lifecycle_status: 'failed', target_country: country })}`, 'TAP alerts failed outcomes'),
  ]);
  const items = Array.isArray(queueData.items) ? queueData.items : [];
  const channels = new Set(items.flatMap(item => item.metadata?.channels || []));
  renderTapSummary(countsData.counts || {}, channels.size);
  document.getElementById('tap-alert-list').innerHTML = items.length ? items.map(item => `<div class="tap-alert-item"><div class="tap-alert-title">${safeHtml(item.keyword || 'Untitled alert')}</div><div class="tap-alert-body">${safeHtml(item.alert_message || 'Queued TAP alert')}</div><div class="tap-meta"><span class="tap-chip">${safeHtml(item.lifecycle_status || 'queued')}</span><span class="tap-chip">priority ${safeHtml(item.priority ?? '-')}</span></div></div>`).join('') : `<div class="tap-alert-item"><div class="tap-alert-title">${safeHtml(tapAlertEmptyTitle(lifecycle, country))}</div><div class="tap-alert-body">Fresh TAP signals will appear here once the queue is refilled.</div></div>`;
  renderOutcomes([...(dispatchedData.items || []), ...(failedData.items || [])]);
  document.getElementById('tap-alert-status').textContent = `${items.length} ${tapAlertLifecycleCopy(lifecycle)} loaded${country ? ` for ${country.toUpperCase()}` : ''}.`;
}

function setTapDispatchBusy(isBusy) {
  ['tap-dispatch-btn', 'tap-dry-run-btn', 'tap-refresh-btn'].forEach(id => { const button = document.getElementById(id); if (button) button.disabled = isBusy; });
  document.getElementById('tap-alert-status')?.setAttribute('aria-busy', isBusy ? 'true' : 'false');
}

function tapDispatchResultMessage(data, dryRun = false) {
  if (dryRun) {
    return `Dry run checked ${(data.items || []).length} alert(s).`;
  }
  const dispatched = Number(data.dispatched || 0);
  const failed = Number(data.failed || 0);
  if (dispatched === 0 && failed === 0) {
    return 'No queued TAP alerts to dispatch.';
  }
  return `Dispatch finished: ${dispatched} sent, ${failed} failed.`;
}

async function dispatchTapAlerts(dryRun = false) {
  const country = getTapTargetCountry();
  const limit = getTapAlertLimit();
  setTapDispatchBusy(true);
  document.getElementById('tap-alert-status').textContent = dryRun ? 'Running dry run...' : 'Dispatching queued alerts...';
  try {
    const data = await fetch(`/api/tap/alerts/dispatch?${buildTapQuery({ limit, dry_run: dryRun ? 'true' : 'false', target_country: country })}`, { method: 'POST' }).then(res => res.json());
    const message = tapDispatchResultMessage(data, dryRun);
    document.getElementById('tap-alert-status').textContent = message;
    toast(message);
    await syncTapOpsView();
    document.getElementById('tap-alert-status').textContent = message;
  } catch {
    const message = dryRun ? 'Dry run failed.' : 'Dispatch failed.';
    document.getElementById('tap-alert-status').textContent = message;
    toast(message);
  } finally {
    setTapDispatchBusy(false);
  }
}

async function syncTapOpsView() {
  clearDegradationsByPrefix('/api/tap/');
  renderTapPresetStrip();
  renderWarnings();
  await Promise.all([loadTapBoard(), loadTapDealRoom(), loadTapAlerts()]);
}

async function init() {
  renderTapPresetStrip();
  renderTapCheckoutReturnNotice();
  await Promise.all([loadStats(), loadPipeline(), loadTrends(), loadCategories(), loadSourceQuality(), loadLogs(), loadAbTest(), loadOperatorReadiness(), syncTapOpsView()]);
  toast('Dashboard loaded.');
}

init().catch(error => {
  console.error('dashboard_init_failed', error);
  document.getElementById('status-pill').textContent = 'Error';
  document.getElementById('status-pill').className = 'status-pill st-error';
});
setInterval(() => { loadPipeline(); loadLogs(); }, 30000);
setInterval(() => { Promise.all([loadStats(), loadTrends(), loadCategories(), loadSourceQuality(), loadOperatorReadiness(), syncTapOpsView()]).then(() => toast('Dashboard data refreshed.')).catch(() => {}); }, 300000);
</script>
</body>
</html>"""
