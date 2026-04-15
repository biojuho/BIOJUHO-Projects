import { PanelState } from './shared.jsx'

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

export function AbPanel({ data, error, onRetry }) {
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
