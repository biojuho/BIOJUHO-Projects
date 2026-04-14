import { Suspense, lazy, useState, useEffect, useCallback, useRef } from 'react'
import { MetricCard } from './components/MetricCard.jsx'
import { Button } from './components/Button.jsx'

const LazyBarChart = lazy(() =>
  import('./components/charts').then((module) => ({ default: module.BarChart })),
)

const LazyDoughnutChart = lazy(() =>
  import('./components/charts').then((module) => ({ default: module.DoughnutChart })),
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
  const abortControllerRef = useRef(null)
  const requestIdRef = useRef(0)

  const runFetch = useCallback(async () => {
    const requestId = requestIdRef.current + 1
    requestIdRef.current = requestId

    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }

    const controller = new AbortController()
    abortControllerRef.current = controller

    setLoading(true)

    try {
      const response = await fetch(url, {
        cache: 'no-store',
        signal: controller.signal,
      })

      if (response.ok === false) {
        throw new Error(`Request failed with status ${response.status}`)
      }

      const payload = await response.json()
      if (requestId !== requestIdRef.current || controller.signal.aborted) {
        return false
      }

      setData(payload)
      setError(null)
      return true
    } catch (e) {
      if (controller.signal.aborted || e.name === 'AbortError') {
        return false
      }

      if (requestId === requestIdRef.current) {
        setError(e.message)
      }
      return false
    } finally {
      if (requestId === requestIdRef.current && !controller.signal.aborted) {
        setLoading(false)
      }
    }
  }, [url])

  useEffect(() => {
    void runFetch()

    return () => {
      requestIdRef.current += 1
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
    }
  }, [runFetch])

  return { data, loading, error, refetch: runFetch }
}

function Loading() {
  return <div className="loading"><div className="spinner" /> 데이터 로딩 중...</div>
}

function PanelState({ error, onRetry }) {
  if (!error) {
    return <Loading />
  }

  return (
    <div className="loading" role="alert">
      <div style={{ display: 'grid', gap: '0.5rem', justifyItems: 'center' }}>
        <strong>Panel unavailable</strong>
        <span style={{ fontSize: '0.75rem', color: '#fca5a5' }}>{error}</span>
        {onRetry ? (
          <Button variant="secondary" size="sm" onClick={() => void onRetry()}>
            Retry panel
          </Button>
        ) : null}
      </div>
    </div>
  )
}

function ChartLoading({ height = 220 }) {
  return (
    <div className="loading" style={{ height, fontSize: '0.75rem' }}>
      <div className="spinner" /> Loading chart...
    </div>
  )
}

// StatusCard → MetricCard 컴포넌트로 대체됨 (하단 참조)

/* ─── GetDayTrends Panel ─── */
function GdtPanel({ data, error, onRetry }) {
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

/* ─── CIE Panel ─── */
function CiePanel({ data, error, onRetry }) {
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

/* ─── AgriGuard Panel ─── */
function AgriGuardPanel({ data, error, onRetry }) {
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

/* ─── Cost Panel ─── */
function CostPanel({ data, error, onRetry }) {
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

/* ─── A/B Performance Panel ─── */
const PATTERN_LABELS = {
  // hooks
  question: '질문형', statistic: '통계형', story: '스토리형',
  bold_claim: '도발형', empathy: '공감형',
  // kicks
  call_to_action: '행동유도', thought_provoker: '사고유발',
  cliffhanger: '클리프행어', summary: '요약형', question_kick: '질문형',
  // angles
  reversal: '반전시각', data_punch: '데이터펀치',
  tips: '실용팁', debate: '논쟁유발',
}
const label = (k) => PATTERN_LABELS[k] || k

function PatternRow({ name, count, avgEng }) {
  const pct = Math.min(Math.round((avgEng || 0) * 100), 100)
  return (
    <div style={{ marginBottom: '0.4rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
        <span style={{ fontSize: '0.72rem', color: '#94a3b8' }}>{label(name)}</span>
        <span style={{ fontSize: '0.72rem', color: '#e2e8f0' }}>
          {pct}% eng · {count}건
        </span>
      </div>
      <div style={{ height: 4, background: 'rgba(148,163,184,0.1)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: 'linear-gradient(90deg,#818cf8,#22d3ee)', borderRadius: 2 }} />
      </div>
    </div>
  )
}

function AbPanel({ data, error, onRetry }) {
  if (!data) return <PanelState error={error} onRetry={onRetry} />

  const fb = data.feedback || {}
  const hasFeedback = fb.total > 0

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>🔁 A/B 패턴 성과</h2>
        <span className="badge">{data.total_samples?.toLocaleString() || 0} 샘플</span>
      </div>

      {/* CIE 역피드백 요약 */}
      <div style={{ background: 'rgba(99,102,241,0.08)', borderRadius: 8, padding: '0.6rem 0.8rem', marginBottom: '0.8rem' }}>
        <div style={{ fontSize: '0.68rem', color: '#818cf8', marginBottom: '0.3rem', fontWeight: 600 }}>
          CIE → GDT 역피드백 (30일)
        </div>
        {hasFeedback ? (
          <>
            <div className="metric-row">
              <span className="metric-label">역주입 건수</span>
              <span className="metric-value">{fb.total}</span>
            </div>
            <div className="metric-row">
              <span className="metric-label">평균 QA 점수</span>
              <span className={`metric-value ${fb.avg_qa >= 80 ? 'success' : fb.avg_qa >= 70 ? 'warning' : 'danger'}`}>
                {Math.round(fb.avg_qa || 0)}/100
              </span>
            </div>
            <div className="metric-row">
              <span className="metric-label">재생성 비율</span>
              <span className="metric-value">{fb.total > 0 ? Math.round(fb.regenerated_count / fb.total * 100) : 0}%</span>
            </div>
          </>
        ) : (
          <div style={{ fontSize: '0.72rem', color: '#64748b' }}>역피드백 데이터 없음 (CIE 실행 후 축적)</div>
        )}
      </div>

      {/* Hook 패턴 */}
      {data.hook_stats?.length > 0 && (
        <>
          <h3 style={{ fontSize: '0.7rem', color: '#818cf8', marginBottom: '0.4rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            훅 패턴 성과순
          </h3>
          {data.hook_stats.slice(0, 4).map((s, i) => (
            <PatternRow key={i} name={s.hook_pattern} count={s.count} avgEng={s.avg_eng} />
          ))}
        </>
      )}

      {/* Angle 패턴 */}
      {data.angle_stats?.length > 0 && (
        <>
          <h3 style={{ fontSize: '0.7rem', color: '#22d3ee', marginBottom: '0.4rem', marginTop: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            앵글 성과순
          </h3>
          {data.angle_stats.slice(0, 3).map((s, i) => (
            <PatternRow key={i} name={s.angle_type} count={s.count} avgEng={s.avg_eng} />
          ))}
        </>
      )}

      {!data.hook_stats?.length && !data.angle_stats?.length && (
        <div style={{ fontSize: '0.72rem', color: '#64748b', padding: '0.5rem 0' }}>
          X 참여 지표 수집 후 표시됩니다
        </div>
      )}
    </div>
  )
}

/* ─── DailyNews Panel ─── */
function DailyNewsPanel({ data, error, onRetry }) {
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

/* ─── Quality Analytics Panel ─── */
function QualityPanel({ data, error, onRetry }) {
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

/* ─── SLA Panel ─── */
function SlaPanel({ data, error, onRetry }) {
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
