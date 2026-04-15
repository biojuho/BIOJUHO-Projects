import { useState, useEffect, useCallback, useRef } from 'react'
import { MetricCard } from './components/MetricCard.jsx'
import { Button } from './components/Button.jsx'
import { useFetch } from './hooks/useFetch.js'
import { GdtPanel } from './components/GdtPanel.jsx'
import { CiePanel } from './components/CiePanel.jsx'
import { AgriGuardPanel } from './components/AgriGuardPanel.jsx'
import { CostPanel } from './components/CostPanel.jsx'
import { AbPanel } from './components/AbPanel.jsx'
import { DailyNewsPanel } from './components/DailyNewsPanel.jsx'
import { QualityPanel } from './components/QualityPanel.jsx'
import { SlaPanel } from './components/SlaPanel.jsx'

/* ═════════════════════════════════════
   Main App
   ═════════════════════════════════════ */
export default function App() {
  const overview = useFetch('/api/overview')
  const gdt = useFetch('/api/getdaytrends')
  const cie = useFetch('/api/cie')
  const ag = useFetch('/api/agriguard')
  const costs = useFetch('/api/costs')
  const dn = useFetch('/api/dailynews')
  const ab = useFetch('/api/ab_performance')
  const quality = useFetch('/api/quality_overview')
  const sla = useFetch('/api/sla_status')

  const [lastUpdated, setLastUpdated] = useState(new Date())

  const refreshAll = useCallback(async () => {
    const results = await Promise.all([
      overview.refetch(),
      gdt.refetch(),
      cie.refetch(),
      ag.refetch(),
      costs.refetch(),
      dn.refetch(),
      ab.refetch(),
      quality.refetch(),
      sla.refetch(),
    ])

    if (results.every(Boolean)) {
      setLastUpdated(new Date())
    }
  }, [overview, gdt, cie, ag, costs, dn, ab, quality, sla])

  // [QA 수정] useRef로 stale closure 방지
  const refreshRef = useRef(refreshAll)
  useEffect(() => { refreshRef.current = refreshAll }, [refreshAll])

  // 30초마다 자동 새로고침
  useEffect(() => {
    const id = setInterval(() => refreshRef.current(), 30_000)
    return () => clearInterval(id)
  }, [])

  const projects = overview.data?.projects || {}

  return (
    <>
      <header className="header">
        <div>
          <h1>AI Projects Dashboard</h1>
          <div className="subtitle">BIOJUHO Lab — 통합 모니터링</div>
        </div>
        <div className="header-right">
          <div className="status-indicator">
            <span className="status-dot" aria-hidden="true" />
            LIVE
          </div>
          <span className="last-updated">
            {lastUpdated.toLocaleTimeString('ko-KR')} 업데이트
          </span>
          <Button
            variant="secondary"
            size="sm"
            onClick={refreshAll}
            leftIcon="↻"
            aria-label="데이터 새로고침"
          >
            새로고침
          </Button>
        </div>
      </header>

      {/* ── Status Overview ── */}
      <section className="status-bar">
        <MetricCard
          icon="📡"
          name="GetDayTrends"
          value={projects.getdaytrends?.total_runs || '—'}
          detail={projects.getdaytrends?.latest_run?.started_at?.slice(0, 16) || ''}
          status={(projects.getdaytrends?.status || 'warn').toLowerCase()}
          badge={(projects.getdaytrends?.status || 'warn').toUpperCase()}
          progress={projects.getdaytrends?.total_runs ? Math.min(100, (projects.getdaytrends.total_runs / 100) * 100) : 0}
        />
        <MetricCard
          icon="✍️"
          name="CIE v2.0"
          value={`QA ${projects.cie?.avg_qa_score || 0}`}
          detail={`${projects.cie?.total_contents || 0} 콘텐츠`}
          status={(projects.cie?.status || 'warn').toLowerCase()}
          badge={(projects.cie?.status || 'WARN').toUpperCase()}
          progress={projects.cie?.avg_qa_score || 0}
        />
        <MetricCard
          icon="🌱"
          name="AgriGuard"
          value={projects.agriguard?.sensor_readings?.toLocaleString() || '—'}
          detail={`${projects.agriguard?.products || 0}개 제품`}
          status={(projects.agriguard?.status || 'error').toLowerCase()}
          badge={(projects.agriguard?.status || 'error').toUpperCase()}
        />
        <MetricCard
          icon="💰"
          name="API 비용"
          value={`$${(projects.costs?.total_cost || 0).toFixed(2)}`}
          detail={`${projects.costs?.total_calls || 0} 호출`}
          status={(projects.costs?.total_cost || 0) > 2 ? 'warn' : 'ok'}
          trend={{
            direction: (projects.costs?.total_cost || 0) > 1.5 ? 'up' : 'flat',
            label: `일예산 $2.00 대비`,
          }}
          progress={Math.min(100, ((projects.costs?.total_cost || 0) / 2) * 100)}
        />
      </section>

      {/* ── Detail Panels ── */}
      <section className="dashboard-grid">
        <SlaPanel data={sla.data} error={sla.error} onRetry={sla.refetch} />
        <GdtPanel data={gdt.data} error={gdt.error} onRetry={gdt.refetch} />
        <CiePanel data={cie.data} error={cie.error} onRetry={cie.refetch} />
        <QualityPanel data={quality.data} error={quality.error} onRetry={quality.refetch} />
        <AbPanel data={ab.data} error={ab.error} onRetry={ab.refetch} />
        <AgriGuardPanel data={ag.data} error={ag.error} onRetry={ag.refetch} />
        <CostPanel data={costs.data} error={costs.error} onRetry={costs.refetch} />
        <DailyNewsPanel data={dn.data} error={dn.error} onRetry={dn.refetch} />
      </section>

      <footer className="footer">
        AI Projects Dashboard v1.0 — BIOJUHO Lab © 2026
      </footer>
    </>
  )
}
