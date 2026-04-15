import { Suspense, lazy } from 'react'
import { PanelState, ChartLoading } from './shared.jsx'
import { CHART_DEFAULTS } from './chartDefaults.js'

const LazyBarChart = lazy(() =>
  import('./charts').then((module) => ({ default: module.BarChart })),
)

export function GdtPanel({ data, error, onRetry }) {
  if (!data) return <PanelState error={error} onRetry={onRetry} />

  const chartData = {
    labels: (data.daily_runs || []).map((r) => r.date?.slice(5)),
    datasets: [
      {
        label: '트렌드',
        data: (data.daily_runs || []).map((r) => r.trends),
        backgroundColor: 'rgba(99,102,241,0.4)',
        borderColor: '#818cf8',
        borderWidth: 2,
        borderRadius: 6,
      },
      {
        label: '트윗',
        data: (data.daily_runs || []).map((r) => r.tweets),
        backgroundColor: 'rgba(34,211,238,0.3)',
        borderColor: '#22d3ee',
        borderWidth: 2,
        borderRadius: 6,
      },
    ],
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>📡 GetDayTrends</h2>
        <span className="badge">{data.total_runs} runs</span>
      </div>
      <div className="metric-row">
        <span className="metric-label">총 트렌드</span>
        <span className="metric-value">{data.total_trends?.toLocaleString()}</span>
      </div>
      <div className="metric-row">
        <span className="metric-label">총 트윗</span>
        <span className="metric-value">{data.total_tweets?.toLocaleString()}</span>
      </div>
      <div className="chart-container">
        <Suspense fallback={<ChartLoading height={240} />}>
          <LazyBarChart data={chartData} options={{
            ...CHART_DEFAULTS,
            plugins: { ...CHART_DEFAULTS.plugins, legend: { display: true, position: 'top', labels: { color: '#94a3b8', font: { family: 'Inter', size: 10 }, boxWidth: 12 } } },
          }} />
        </Suspense>
      </div>
      {data.top_trends?.length > 0 && (
        <>
          <h3 style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '1rem', marginBottom: '0.5rem' }}>🔥 최근 트렌드</h3>
          <table className="data-table">
            <thead><tr><th>키워드</th><th>바이럴</th><th>트윗수</th></tr></thead>
            <tbody>
              {data.top_trends.slice(0, 5).map((t, i) => (
                <tr key={i}>
                  <td>{t.keyword}</td>
                  <td>{t.viral_potential}</td>
                  <td>{t.tweet_volume}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  )
}
