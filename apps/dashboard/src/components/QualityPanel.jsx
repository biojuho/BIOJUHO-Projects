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

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>🛡️ Quality Analytics</h2>
        <span className="badge">QA + FactCheck</span>
      </div>

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

      {!data.qa_grades?.length && !data.daily_production?.length && (
        <div style={{ fontSize: '0.72rem', color: '#64748b', padding: '0.5rem 0' }}>
          QA 데이터가 없습니다. 파이프라인 실행 후 표시됩니다.
        </div>
      )}
    </div>
  )
}
