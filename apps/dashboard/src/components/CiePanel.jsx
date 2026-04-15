import { Suspense, lazy } from 'react'
import { PanelState, ChartLoading } from './shared.jsx'
import { DONUT_OPTS } from './chartDefaults.js'

const LazyDoughnutChart = lazy(() =>
  import('./charts').then((module) => ({ default: module.DoughnutChart })),
)

export function CiePanel({ data, error, onRetry }) {
  if (!data) return <PanelState error={error} onRetry={onRetry} />

  const qaData = {
    labels: (data.qa_distribution || []).map((d) => d.grade),
    datasets: [{
      data: (data.qa_distribution || []).map((d) => d.count),
      backgroundColor: ['#34d399', '#818cf8', '#fbbf24', '#fb7185'],
      borderWidth: 0,
    }],
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>✍️ Content Intelligence</h2>
        <span className="badge">v2.0</span>
      </div>
      <div className="metric-row">
        <span className="metric-label">생성된 콘텐츠</span>
        <span className="metric-value">{data.total_contents}</span>
      </div>
      <div className="metric-row">
        <span className="metric-label">수집된 트렌드</span>
        <span className="metric-value">{data.total_trends}</span>
      </div>
      {data.by_platform?.length > 0 && data.by_platform.map((p, i) => (
        <div className="metric-row" key={i}>
          <span className="metric-label">{p.platform?.toUpperCase()}</span>
          <span className={`metric-value ${p.avg_qa >= 80 ? 'success' : p.avg_qa >= 70 ? 'warning' : 'danger'}`}>
            QA {Math.round(p.avg_qa || 0)}/100 ({p.count}건)
          </span>
        </div>
      ))}
      {data.qa_distribution?.length > 0 && (
        <div className="chart-container" style={{ height: 180 }}>
          <Suspense fallback={<ChartLoading height={180} />}>
            <LazyDoughnutChart data={qaData} options={DONUT_OPTS} />
          </Suspense>
        </div>
      )}
    </div>
  )
}
