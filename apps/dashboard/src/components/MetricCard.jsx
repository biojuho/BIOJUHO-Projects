/**
 * MetricCard — BIOJUHO AI Ops Design System
 *
 * 핵심 정보 표시 카드 컴포넌트.
 * 상태(ok/warn/error/info), 트렌드 방향, 프로그레스, 배지를 지원합니다.
 *
 * @example
 * <MetricCard
 *   icon="✅"
 *   name="Tests Passed"
 *   value="1,220"
 *   detail="216 + 602 + 402"
 *   status="ok"
 *   badge="GREEN"
 *   trend={{ direction: 'up', label: '+4 since yesterday' }}
 *   progress={91}
 * />
 */

import { useState } from 'react';

/* ─────────────────────────────────────────────────────────
   MetricCard
   ───────────────────────────────────────────────────────── */
export function MetricCard({
  icon       = '📊',
  name       = 'Metric',
  value      = '—',
  detail     = '',
  status     = 'info',   // 'ok' | 'warn' | 'error' | 'info'
  badge      = null,     // string | null
  trend      = null,     // { direction: 'up'|'down'|'flat', label: string }
  progress   = null,     // 0–100 | null
  onClick    = null,
  className  = '',
}) {
  const [hovered, setHovered] = useState(false);

  const trendConfig = {
    up:   { symbol: '↑', style: { color: 'var(--color-success)' } },
    down: { symbol: '↓', style: { color: 'var(--color-danger)'  } },
    flat: { symbol: '→', style: { color: 'var(--color-text-muted)' } },
  };

  return (
    <article
      className={`status-card ${status} ${className}`}
      style={{ cursor: onClick ? 'pointer' : 'default' }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={onClick}
      aria-label={`${name}: ${value}`}
    >
      {/* Icon */}
      <span className="icon" aria-hidden="true">{icon}</span>

      {/* Label */}
      <p className="name">{name}</p>

      {/* Main Value */}
      <p
        className="value"
        style={{
          transition: 'transform 0.2s ease',
          transform: hovered ? 'scale(1.04)' : 'scale(1)',
        }}
      >
        {value}
      </p>

      {/* Detail / subtitle */}
      {detail && (
        <p className="detail">{detail}</p>
      )}

      {/* Trend indicator */}
      {trend && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          marginTop: '6px',
        }}>
          <span
            style={{
              fontSize: 'var(--text-xs)',
              fontWeight: 'var(--font-semibold)',
              ...trendConfig[trend.direction]?.style,
            }}
            aria-label={`Trend: ${trend.direction}`}
          >
            {trendConfig[trend.direction]?.symbol}
          </span>
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)' }}>
            {trend.label}
          </span>
        </div>
      )}

      {/* Progress bar */}
      {progress !== null && (
        <div className="progress-bar" style={{ marginTop: '10px' }} aria-label={`Progress: ${progress}%`}>
          <div
            className={`progress-fill ${status === 'ok' ? 'success' : status === 'warn' ? 'warning' : status === 'error' ? 'danger' : ''}`}
            style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
          />
        </div>
      )}

      {/* Status badge */}
      {badge && (
        <div style={{ marginTop: '8px' }}>
          <span className={`status-badge ${status}`}>{badge}</span>
        </div>
      )}
    </article>
  );
}


/* ─────────────────────────────────────────────────────────
   InfoPanel — 제목 + 내용 영역을 감싸는 Glass Panel
   ───────────────────────────────────────────────────────── */
export function InfoPanel({
  title,
  badge     = null,
  children,
  className = '',
  fullWidth = false,
  headerRight = null,
}) {
  return (
    <section
      className={`panel ${fullWidth ? 'span-2' : ''} ${className}`}
      aria-labelledby={`panel-${title?.replace(/\s+/g, '-').toLowerCase()}`}
    >
      <div className="panel-header">
        <h2 id={`panel-${title?.replace(/\s+/g, '-').toLowerCase()}`}>
          {title}
          {badge && (
            <span className="badge" style={{ marginLeft: '8px' }}>{badge}</span>
          )}
        </h2>
        {headerRight && (
          <div>{headerRight}</div>
        )}
      </div>
      {children}
    </section>
  );
}


/* ─────────────────────────────────────────────────────────
   MetricRow — panel 내부에서 쓰이는 key-value 행
   ───────────────────────────────────────────────────────── */
export function MetricRow({
  label,
  value,
  valueVariant = '', // 'success' | 'warning' | 'danger' | 'info' | 'mono'
}) {
  return (
    <div className="metric-row">
      <span className="metric-label">{label}</span>
      <span className={`metric-value ${valueVariant}`}>{value}</span>
    </div>
  );
}


/* ─────────────────────────────────────────────────────────
   SkeletonCard — 로딩 플레이스홀더
   ───────────────────────────────────────────────────────── */
export function SkeletonCard({ height = '80px' }) {
  return (
    <div
      className="skeleton"
      style={{ height, width: '100%' }}
      aria-busy="true"
      aria-label="Loading..."
      role="status"
    />
  );
}
