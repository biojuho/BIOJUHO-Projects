import { Suspense, lazy } from 'react'
import { PanelState, ChartLoading } from './shared.jsx'
import { CHART_DEFAULTS, DONUT_OPTS } from './chartDefaults.js'

const LazyBarChart = lazy(() =>
  import('./charts').then((module) => ({ default: module.BarChart })),
)
const LazyDoughnutChart = lazy(() =>
  import('./charts').then((module) => ({ default: module.DoughnutChart })),
)

export function QualityPanel({ data, error, onRetry }) {
  if (!data) return <PanelState error={error} onRetry={onRetry} />

  const gradeColors = ['#34d399', '#818cf8', '#fbbf24', '#fb7185']
  const gradeData = {
    labels: (data.qa_grades || []).map(g => g.grade),
    datasets: [{
      data: (data.qa_grades || []).map(g => g.count),
      backgroundColor: gradeColors,
      borderWidth: 0,
    }],
  }

  const prodChartData = {
    labels: (data.daily_production || []).map(d => d.date?.slice(5)),
    datasets: [
      {
        label: '생성',
        data: (data.daily_production || []).map(d => d.drafts),
        backgroundColor: 'rgba(99,102,241,0.4)',
        borderColor: '#818cf8',
        borderWidth: 2,
        borderRadius: 6,
      },
      {
        label: '승인',
        data: (data.daily_production || []).map(d => d.approved),
        backgroundColor: 'rgba(52,211,153,0.4)',
        borderColor: '#34d399',
        borderWidth: 2,
        borderRadius: 6,
      },
    ],
  }

  const blockers = data.top_blocking_reasons || []
  const maxBlockCount = blockers.length > 0 ? blockers[0].count : 1
  const smoke = data.workspace_smoke || null
  const smokeSummary = smoke?.summary || {}
  const smokePassed = smokeSummary.passed ?? 0
  const smokeTotal = smokeSummary.total ?? 0
  const smokeLabel = smoke?.status === 'partial'
    ? 'PARTIAL'
    : smoke?.available && smokePassed === smokeTotal && smokeTotal > 0
      ? 'PASS'
      : smoke?.available
        ? 'FAIL'
        : 'NO REPORT'
  const smokeBadgeClass = smokeLabel === 'PASS' ? 'ok' : smokeLabel === 'PARTIAL' ? 'warn' : 'error'
  const slowestChecks = smoke?.slowest_checks || []
  const mcpTrace = smoke?.mcp_trace || null
  const mcpTraceEnabled = Boolean(mcpTrace?.enabled)
  const mcpTracePassed = mcpTrace?.passed ?? 0
  const mcpTraceCompleted = mcpTrace?.completed ?? 0
  const mcpTraceFailed = mcpTrace?.failed ?? 0
  const mcpTraceLabel = mcpTraceEnabled
    ? mcpTraceFailed === 0
      ? 'PASS'
      : 'FAIL'
    : 'NO TRACE'
  const mcpTraceBadgeClass = mcpTraceLabel === 'PASS' ? 'ok' : mcpTraceLabel === 'FAIL' ? 'error' : 'warn'
  const mcpTraceChecks = mcpTrace?.checks || []
  const devStatus = data.dev_server_status || null
  const devSummary = devStatus?.summary || {}
  const devReady = devSummary.ready ?? 0
  const devTotal = devSummary.total ?? 0
  const devUnready = devSummary.unready ?? 0
  const devLabel = devStatus?.available
    ? devUnready === 0 && devTotal > 0
      ? 'READY'
      : 'DEGRADED'
    : 'NO STATUS'
  const devBadgeClass = devLabel === 'READY' ? 'ok' : devLabel === 'DEGRADED' ? 'warn' : 'error'
  const devTargets = devStatus?.unready_targets?.length > 0
    ? devStatus.unready_targets
    : devStatus?.targets || []
  const credentialBoundaries = data.credential_boundaries || null
  const credentialBoundaryItems = credentialBoundaries?.boundaries || []
  const credentialBoundaryTotal = credentialBoundaries?.boundary_count ?? 0
  const credentialMissingEnv = credentialBoundaries?.missing_required_env_count ?? 0
  const credentialNextUnblock = credentialBoundaries?.next_unblock || null
  const credentialNextEnvNames = (credentialNextUnblock?.env_names || []).join(', ')
  const credentialNextCommand = credentialNextUnblock?.first_verification_command || ''
  const credentialNextLiveStatus = String(credentialNextUnblock?.live_status || '').replaceAll('_', ' ')
  const credentialNextCommandCount = credentialNextUnblock?.verification_command_count ?? 0
  const credentialNextPlanSummary = credentialNextUnblock
    ? [
        credentialNextUnblock.plan_rank ? `Rank ${credentialNextUnblock.plan_rank}` : '',
        credentialNextCommandCount ? `${credentialNextCommandCount} ${credentialNextCommandCount === 1 ? 'command' : 'commands'}` : '',
        credentialNextLiveStatus,
      ].filter(Boolean).join(' / ')
    : ''
  const credentialLabel = credentialBoundaries?.available
    ? credentialMissingEnv > 0
      ? 'ACTION'
      : 'TRACKED'
    : 'NO REPORT'
  const credentialBadgeClass = credentialLabel === 'TRACKED' ? 'ok' : credentialLabel === 'ACTION' ? 'warn' : 'error'

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>🛡️ Quality Analytics</h2>
        <span className="badge">QA + FactCheck</span>
      </div>

      {smoke && (
        <>
          <h3 style={{ fontSize: '0.7rem', color: '#22d3ee', marginBottom: '0.4rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Workspace Smoke
          </h3>
          <div className="metric-row">
            <span className="metric-label">Latest gate</span>
            <span className={`status-badge ${smokeBadgeClass}`}>
              {smokeTotal ? `${smokePassed}/${smokeTotal} ${smokeLabel}` : smokeLabel}
            </span>
          </div>
          <div className="metric-row">
            <span className="metric-label">Duration</span>
            <span className="metric-value">{(smoke.duration_seconds || 0).toFixed(1)}s</span>
          </div>
          {slowestChecks.length > 0 && (
            <table className="data-table" style={{ marginTop: '0.45rem', marginBottom: '0.8rem' }}>
              <thead><tr><th>Slowest check</th><th>Scope</th><th>Seconds</th></tr></thead>
              <tbody>
                {slowestChecks.slice(0, 3).map((check, i) => (
                  <tr key={`${check.scope}-${check.name}-${i}`}>
                    <td>{check.name}</td>
                    <td>{check.scope}</td>
                    <td>{(check.elapsed_seconds || 0).toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {mcpTraceEnabled && (
            <>
              <h3 style={{ fontSize: '0.7rem', color: '#38bdf8', marginBottom: '0.4rem', marginTop: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                MCP Trace
              </h3>
              <div className="metric-row">
                <span className="metric-label">MCP checks</span>
                <span className={`status-badge ${mcpTraceBadgeClass}`}>
                  {mcpTraceCompleted ? `${mcpTracePassed}/${mcpTraceCompleted} ${mcpTraceLabel}` : mcpTraceLabel}
                </span>
              </div>
              <div className="metric-row">
                <span className="metric-label">MCP elapsed</span>
                <span className="metric-value">{(mcpTrace.elapsed_seconds || 0).toFixed(1)}s</span>
              </div>
              {mcpTraceChecks.length > 0 && (
                <table className="data-table" style={{ marginTop: '0.45rem', marginBottom: '0.8rem' }}>
                  <thead><tr><th>Check</th><th>Kind</th><th>Seconds</th></tr></thead>
                  <tbody>
                    {mcpTraceChecks.slice(0, 3).map((check, i) => (
                      <tr key={`${check.name}-${i}`}>
                        <td>{check.name}</td>
                        <td>{check.command_kind}</td>
                        <td>{(check.elapsed_seconds || 0).toFixed(1)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )}
        </>
      )}

      {devStatus && (
        <>
          <h3 style={{ fontSize: '0.7rem', color: '#34d399', marginBottom: '0.4rem', marginTop: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Dev Servers
          </h3>
          <div className="metric-row">
            <span className="metric-label">Readiness</span>
            <span className={`status-badge ${devBadgeClass}`}>
              {devTotal ? `${devReady}/${devTotal} ${devLabel}` : devLabel}
            </span>
          </div>
          {devTargets.length > 0 && (
            <table className="data-table" style={{ marginTop: '0.45rem', marginBottom: '0.8rem' }}>
              <thead><tr><th>Target</th><th>Project</th><th>State</th></tr></thead>
              <tbody>
                {devTargets.slice(0, 4).map((target, i) => (
                  <tr key={`${target.id}-${i}`}>
                    <td>{target.label || target.id}</td>
                    <td>{target.project}</td>
                    <td>{target.ok ? 'ready' : target.error || 'unready'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}

      {credentialBoundaries && (
        <>
          <h3 style={{ fontSize: '0.7rem', color: '#fbbf24', marginBottom: '0.4rem', marginTop: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Credential Boundaries
          </h3>
          <div className="metric-row">
            <span className="metric-label">Operator blockers</span>
            <span className={`status-badge ${credentialBadgeClass}`}>
              {credentialBoundaryTotal ? `${credentialBoundaryTotal} ${credentialLabel}` : credentialLabel}
            </span>
          </div>
          <div className="metric-row">
            <span className="metric-label">Missing env names</span>
            <span className="metric-value">{credentialMissingEnv}</span>
          </div>
          {credentialNextUnblock && (
            <>
              <div className="metric-row">
                <span className="metric-label">Next Unblock</span>
                <span className="metric-value" style={{ maxWidth: '58%', textAlign: 'right', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {credentialNextUnblock.title || credentialNextUnblock.boundary_id}
                </span>
              </div>
              {credentialNextPlanSummary && (
                <div className="metric-row">
                  <span className="metric-label">Live plan</span>
                  <span className="metric-value" style={{ maxWidth: '58%', textAlign: 'right', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {credentialNextPlanSummary}
                  </span>
                </div>
              )}
              <div className="metric-row">
                <span className="metric-label">Next env</span>
                <span className="metric-value" style={{ maxWidth: '58%', textAlign: 'right', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {credentialNextEnvNames || 'none'}
                </span>
              </div>
              {credentialNextCommand && (
                <div className="metric-row">
                  <span className="metric-label">Next command</span>
                  <span className="metric-value mono" style={{ maxWidth: '58%', textAlign: 'right', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {credentialNextCommand}
                  </span>
                </div>
              )}
            </>
          )}
          {credentialBoundaryItems.length > 0 && (
            <table className="data-table" style={{ marginTop: '0.45rem', marginBottom: '0.8rem' }}>
              <thead><tr><th>Boundary</th><th>Status</th><th>Env</th></tr></thead>
              <tbody>
                {credentialBoundaryItems.slice(0, 4).map((boundary, i) => (
                  <tr key={`${boundary.id}-${i}`}>
                    <td>{boundary.title || boundary.id}</td>
                    <td>{String(boundary.status || '').replaceAll('_', ' ')}</td>
                    <td>{boundary.missing_required_env_count ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}

      {/* QA Grade Distribution */}
      {data.qa_grades?.length > 0 && (
        <>
          <h3 style={{ fontSize: '0.7rem', color: '#818cf8', marginBottom: '0.4rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            QA 등급 분포
          </h3>
          <div className="chart-container" style={{ height: 160 }}>
            <Suspense fallback={<ChartLoading height={160} />}>
              <LazyDoughnutChart data={gradeData} options={DONUT_OPTS} />
            </Suspense>
          </div>
        </>
      )}

      {/* Daily Production */}
      {data.daily_production?.length > 0 && (
        <>
          <h3 style={{ fontSize: '0.7rem', color: '#22d3ee', marginBottom: '0.4rem', marginTop: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            일별 생산량 (7일)
          </h3>
          <div className="chart-container" style={{ height: 160 }}>
            <Suspense fallback={<ChartLoading height={160} />}>
              <LazyBarChart data={prodChartData} options={{
                ...CHART_DEFAULTS,
                plugins: { ...CHART_DEFAULTS.plugins, legend: { display: true, position: 'top', labels: { color: '#94a3b8', font: { family: 'Inter', size: 10 }, boxWidth: 12 } } },
              }} />
            </Suspense>
          </div>
        </>
      )}

      {/* Top Blocking Reasons */}
      {blockers.length > 0 && (
        <>
          <h3 style={{ fontSize: '0.7rem', color: '#fb7185', marginBottom: '0.4rem', marginTop: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Top 차단 사유
          </h3>
          {blockers.slice(0, 5).map((b, i) => {
            const pct = Math.round((b.count / maxBlockCount) * 100)
            return (
              <div key={i} style={{ marginBottom: '0.4rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
                  <span style={{ fontSize: '0.68rem', color: '#94a3b8', maxWidth: '70%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{b.reason}</span>
                  <span style={{ fontSize: '0.68rem', color: '#e2e8f0' }}>{b.count}건</span>
                </div>
                <div style={{ height: 4, background: 'rgba(148,163,184,0.1)', borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${pct}%`, background: 'linear-gradient(90deg,#fb7185,#fbbf24)', borderRadius: 2 }} />
                </div>
              </div>
            )
          })}
        </>
      )}

      {/* Confidence Distribution */}
      {data.confidence_distribution?.length > 0 && (
        <>
          <h3 style={{ fontSize: '0.7rem', color: '#34d399', marginBottom: '0.4rem', marginTop: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            트렌드 신뢰도 분포
          </h3>
          {data.confidence_distribution.map((c, i) => (
            <div className="metric-row" key={i}>
              <span className="metric-label">{c.tier}</span>
              <span className="metric-value">{c.count}</span>
            </div>
          ))}
        </>
      )}

      {/* Lifecycle */}
      {data.lifecycle_distribution?.length > 0 && (
        <>
          <h3 style={{ fontSize: '0.7rem', color: '#94a3b8', marginBottom: '0.4rem', marginTop: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            파이프라인 현황
          </h3>
          <table className="data-table">
            <thead><tr><th>Lifecycle</th><th>Review</th><th>수량</th></tr></thead>
            <tbody>
              {data.lifecycle_distribution.slice(0, 6).map((l, i) => (
                <tr key={i}>
                  <td>{l.lifecycle_status || '—'}</td>
                  <td>{l.review_status || '—'}</td>
                  <td>{l.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {!data.qa_grades?.length && !data.daily_production?.length && !smoke?.available && !devStatus?.available && !credentialBoundaries?.available && (
        <div style={{ fontSize: '0.72rem', color: '#64748b', padding: '0.5rem 0' }}>
          QA 데이터가 없습니다. 파이프라인 실행 후 표시됩니다.
        </div>
      )}
    </div>
  )
}
