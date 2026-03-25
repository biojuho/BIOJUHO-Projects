import { useState, useEffect, useCallback, useRef } from 'react'
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, LineElement,
  PointElement, ArcElement, Tooltip, Legend, Filler,
} from 'chart.js'
import { Bar, Line, Doughnut } from 'react-chartjs-2'

ChartJS.register(
  CategoryScale, LinearScale, BarElement, LineElement,
  PointElement, ArcElement, Tooltip, Legend, Filler
)

const CHART_DEFAULTS = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: {
      backgroundColor: 'rgba(17,24,39,0.95)',
      borderColor: 'rgba(99,102,241,0.3)',
      borderWidth: 1,
      titleFont: { family: 'Inter', size: 12 },
      bodyFont: { family: 'Inter', size: 11 },
      padding: 10,
      cornerRadius: 8,
    },
  },
  scales: {
    x: {
      grid: { color: 'rgba(148,163,184,0.06)' },
      ticks: { color: '#64748b', font: { family: 'Inter', size: 10 } },
    },
    y: {
      grid: { color: 'rgba(148,163,184,0.06)' },
      ticks: { color: '#64748b', font: { family: 'Inter', size: 10 } },
    },
  },
}

const DONUT_OPTS = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'bottom',
      labels: { color: '#94a3b8', font: { family: 'Inter', size: 11 }, padding: 15 },
    },
    tooltip: CHART_DEFAULTS.plugins.tooltip,
  },
  cutout: '65%',
}

function useFetch(url) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const refetch = useCallback(() => {
    setLoading(true)
    fetch(url)
      .then((r) => r.json())
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [url])

  useEffect(() => { refetch() }, [refetch])
  return { data, loading, error, refetch }
}

function Loading() {
  return <div className="loading"><div className="spinner" /> 데이터 로딩 중...</div>
}

function StatusCard({ icon, name, value, detail, status = 'ok' }) {
  return (
    <div className={`status-card ${status}`}>
      <div className="icon">{icon}</div>
      <div className="name">{name}</div>
      <div className="value">{value}</div>
      {detail && <div className="detail">{detail}</div>}
    </div>
  )
}

/* ─── GetDayTrends Panel ─── */
function GdtPanel({ data }) {
  if (!data) return <Loading />

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
        <Bar data={chartData} options={{
          ...CHART_DEFAULTS,
          plugins: { ...CHART_DEFAULTS.plugins, legend: { display: true, position: 'top', labels: { color: '#94a3b8', font: { family: 'Inter', size: 10 }, boxWidth: 12 } } },
        }} />
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

/* ─── CIE Panel ─── */
function CiePanel({ data }) {
  if (!data) return <Loading />

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
          <Doughnut data={qaData} options={DONUT_OPTS} />
        </div>
      )}
    </div>
  )
}

/* ─── AgriGuard Panel ─── */
function AgriGuardPanel({ data }) {
  if (!data) return <Loading />

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

/* ─── Cost Panel ─── */
function CostPanel({ data }) {
  if (!data) return <Loading />

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
          <Doughnut data={chartData} options={DONUT_OPTS} />
        </div>
      ) : (
        <div className="loading" style={{ height: 100, fontSize: '0.75rem' }}>
          비용 데이터 없음 (telemetry 로그가 비어 있음)
        </div>
      )}
    </div>
  )
}

/* ─── DailyNews Panel ─── */
function DailyNewsPanel({ data }) {
  if (!data) return <Loading />

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

/* ═════════════════════════════════
   Main App
   ═════════════════════════════════ */
export default function App() {
  const overview = useFetch('/api/overview')
  const gdt = useFetch('/api/getdaytrends')
  const cie = useFetch('/api/cie')
  const ag = useFetch('/api/agriguard')
  const costs = useFetch('/api/costs')
  const dn = useFetch('/api/dailynews')

  const [lastUpdated, setLastUpdated] = useState(new Date())

  const refreshAll = useCallback(() => {
    overview.refetch()
    gdt.refetch()
    cie.refetch()
    ag.refetch()
    costs.refetch()
    dn.refetch()
    setLastUpdated(new Date())
  }, [overview, gdt, cie, ag, costs, dn])

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
          <span className="last-updated">
            마지막 업데이트: {lastUpdated.toLocaleTimeString('ko-KR')}
          </span>
          <button className="refresh-btn" onClick={refreshAll}>
            ↻ 새로고침
          </button>
        </div>
      </header>

      {/* ── Status Overview ── */}
      <section className="status-bar">
        <StatusCard
          icon="📡"
          name="GetDayTrends"
          value={projects.getdaytrends?.total_runs || '—'}
          detail={projects.getdaytrends?.latest_run?.started_at?.slice(0, 16) || ''}
          status={(projects.getdaytrends?.status || 'warn').toLowerCase()}
        />
        <StatusCard
          icon="✍️"
          name="CIE v2.0"
          value={`QA ${projects.cie?.avg_qa_score || 0}`}
          detail={`${projects.cie?.total_contents || 0} 콘텐츠`}
          status={(projects.cie?.status || 'warn').toLowerCase()}
        />
        <StatusCard
          icon="🌱"
          name="AgriGuard"
          value={projects.agriguard?.sensor_readings?.toLocaleString() || '—'}
          detail={`${projects.agriguard?.products || 0}개 제품`}
          status={(projects.agriguard?.status || 'error').toLowerCase()}
        />
        <StatusCard
          icon="💰"
          name="API 비용"
          value={`$${(projects.costs?.total_cost || 0).toFixed(2)}`}
          detail={`${projects.costs?.total_calls || 0} 호출`}
          status={(projects.costs?.total_cost || 0) > 2 ? 'warn' : 'ok'}
        />
      </section>

      {/* ── Detail Panels ── */}
      <section className="dashboard-grid">
        <GdtPanel data={gdt.data} />
        <CiePanel data={cie.data} />
        <AgriGuardPanel data={ag.data} />
        <CostPanel data={costs.data} />
        <DailyNewsPanel data={dn.data} />
      </section>

      <footer className="footer">
        AI Projects Dashboard v1.0 — BIOJUHO Lab © 2026
      </footer>
    </>
  )
}
