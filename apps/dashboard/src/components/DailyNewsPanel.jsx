import { PanelState } from './shared.jsx'

export function DailyNewsPanel({ data, error, onRetry }) {
  if (!data) return <PanelState error={error} onRetry={onRetry} />

  const counts = data.table_counts || {}

  return (
    <div className="panel full-width">
      <div className="panel-header">
        <h2>📰 DailyNews</h2>
        <span className="badge">{data.tables?.length || 0} tables</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.5rem' }}>
        {Object.entries(counts).map(([name, count]) => (
          <div className="metric-row" key={name} style={{ padding: '0.4rem 0' }}>
            <span className="metric-label" style={{ fontSize: '0.72rem' }}>{name}</span>
            <span className="metric-value" style={{ fontSize: '0.85rem' }}>{count?.toLocaleString()}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
