import { PanelState } from './shared.jsx'

export function SlaPanel({ data, error, onRetry }) {
  if (!data) return <PanelState error={error} onRetry={onRetry} />

  const pipelines = data.pipelines || []
  const target = data.sla_target || 99

  return (
    <div className="panel" style={{ gridColumn: '1 / -1' }}>
      <div className="panel-header">
        <h2>⚡ 파이프라인 SLA 현황</h2>
        <span className="badge" style={{
          background: data.overall_sla_met ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)',
          color: data.overall_sla_met ? '#22c55e' : '#ef4444',
        }}>
          {data.overall_sla_met ? '✅ SLA 충족' : '⚠️ SLA 미달'} — {data.overall_success_rate}%
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
        {pipelines.map((p) => (
          <div key={p.name} style={{
            background: 'rgba(30,41,59,0.5)',
            borderRadius: '12px',
            padding: '1.25rem',
            border: '1px solid rgba(148,163,184,0.08)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <strong style={{ fontSize: '0.9rem' }}>{p.name}</strong>
              <span style={{
                fontSize: '0.7rem',
                padding: '2px 8px',
                borderRadius: '9999px',
                background: p.sla_met ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)',
                color: p.sla_met ? '#22c55e' : '#ef4444',
              }}>
                {p.sla_met ? 'MET' : 'MISSED'}
              </span>
            </div>

            {/* Success Rate Bar */}
            <div style={{ marginBottom: '0.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: '#94a3b8', marginBottom: '4px' }}>
                <span>성공률</span>
                <span style={{ fontWeight: 600, color: p.success_rate >= target ? '#22c55e' : '#ef4444' }}>
                  {p.success_rate}%
                </span>
              </div>
              <div style={{ height: '6px', borderRadius: '3px', background: 'rgba(148,163,184,0.1)', overflow: 'hidden', position: 'relative' }}>
                <div style={{
                  height: '100%',
                  width: `${Math.min(100, p.success_rate)}%`,
                  borderRadius: '3px',
                  background: p.success_rate >= target
                    ? 'linear-gradient(90deg, #22c55e, #4ade80)'
                    : 'linear-gradient(90deg, #ef4444, #f87171)',
                  transition: 'width 0.6s ease',
                }} />
                {/* Target line */}
                <div style={{
                  position: 'absolute',
                  left: `${target}%`,
                  top: 0,
                  bottom: 0,
                  width: '2px',
                  background: '#f59e0b',
                  opacity: 0.8,
                }} />
              </div>
            </div>

            <div style={{ display: 'flex', gap: '1rem', fontSize: '0.7rem', color: '#64748b' }}>
              <span>{p.total_runs} runs</span>
              <span>{p.successful_runs} pass</span>
              {p.avg_duration_min > 0 && <span>~{p.avg_duration_min}min</span>}
            </div>

            {/* Recent failures */}
            {(p.recent_failures || []).length > 0 && (
              <div style={{ marginTop: '0.75rem', fontSize: '0.7rem' }}>
                <div style={{ color: '#f87171', marginBottom: '4px' }}>최근 장애:</div>
                {p.recent_failures.map((f, i) => (
                  <div key={i} style={{ color: '#94a3b8', padding: '2px 0', borderBottom: '1px solid rgba(148,163,184,0.05)' }}>
                    {f.time?.slice(0, 16) || f.job || ''}
                    {f.error && <span style={{ color: '#fca5a5' }}> — {f.error.slice(0, 60)}</span>}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: '1.5rem', fontSize: '0.75rem', color: '#64748b' }}>
        <span>🎯 SLA 목표: {target}%</span>
        <span>📅 집계 기간: {data.lookback_days}일</span>
        <span>📊 전체 성공률: {data.overall_success_rate}%</span>
      </div>
    </div>
  )
}
