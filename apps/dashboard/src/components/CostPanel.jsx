import { Suspense, lazy } from 'react'
import { PanelState, ChartLoading } from './shared.jsx'
import { DONUT_OPTS } from './chartDefaults.js'

const LazyDoughnutChart = lazy(() =>
  import('./charts').then((module) => ({ default: module.DoughnutChart })),
)

export function CostPanel({ data, error, onRetry }) {
  if (!data) return <PanelState error={error} onRetry={onRetry} />

  const projects = data.projects || {}
  const labels = Object.keys(projects)
  const costs = Object.values(projects).map((p) => p.cost_usd || 0)

  const chartData = {
    labels,
    datasets: [{
      data: costs,
      backgroundColor: ['#818cf8', '#22d3ee', '#34d399', '#fbbf24', '#fb7185'],
      borderWidth: 0,
    }],
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>💰 LLM API 비용</h2>
        <span className="badge">7일</span>
      </div>
      <div className="metric-row">
        <span className="metric-label">총 API 호출</span>
        <span className="metric-value">{data.total_calls || 0}</span>
      </div>
      <div className="metric-row">
        <span className="metric-label">총 비용</span>
        <span className={`metric-value ${(data.total_cost || 0) > 2 ? 'danger' : 'success'}`}>
          ${(data.total_cost || 0).toFixed(4)}
        </span>
      </div>
      {labels.length > 0 ? (
        <div className="chart-container" style={{ height: 180 }}>
          <Suspense fallback={<ChartLoading height={180} />}>
            <LazyDoughnutChart data={chartData} options={DONUT_OPTS} />
          </Suspense>
        </div>
      ) : (
        <div className="loading" style={{ height: 100, fontSize: '0.75rem' }}>
          비용 데이터 없음 (telemetry 로그가 비어 있음)
        </div>
      )}
    </div>
  )
}
