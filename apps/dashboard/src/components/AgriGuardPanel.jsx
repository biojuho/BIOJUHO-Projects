import { PanelState } from './shared.jsx'

export function AgriGuardPanel({ data, error, onRetry }) {
  if (!data) return <PanelState error={error} onRetry={onRetry} />

  const tables = data.tables || {}

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>🌱 AgriGuard</h2>
        <span className="badge">PostgreSQL</span>
      </div>
      {Object.entries(tables).map(([name, count]) => (
        <div className="metric-row" key={name}>
          <span className="metric-label">{name}</span>
          <span className="metric-value">{count?.toLocaleString()}</span>
        </div>
      ))}
      {data.product_stats && (
        <>
          <div className="metric-row">
            <span className="metric-label">인증 제품</span>
            <span className="metric-value success">
              {data.product_stats.verified}/{data.product_stats.total}
            </span>
          </div>
          <div className="metric-row">
            <span className="metric-label">콜드체인</span>
            <span className="metric-value">{data.product_stats.cold_chain}</span>
          </div>
        </>
      )}
    </div>
  )
}
