/**
 * Button — BIOJUHO AI Ops Design System
 *
 * 모든 액션에서 사용되는 단일 버튼 컴포넌트.
 * variant, size, loading, icon 조합을 지원합니다.
 *
 * @example — Primary CTA
 * <Button variant="primary" onClick={handleRefresh}>
 *   Refresh Data
 * </Button>
 *
 * @example — Loading state (async 처리 중)
 * <Button variant="primary" loading>
 *   Syncing...
 * </Button>
 *
 * @example — Icon-only ghost button
 * <Button variant="ghost" size="icon" aria-label="Settings">
 *   ⚙
 * </Button>
 *
 * @example — Danger with confirmation
 * <Button variant="danger" size="sm" onClick={handleDelete}>
 *   Delete
 * </Button>
 */

import { useState } from 'react';

/* ─────────────────────────────────────────────────────────
   Ripple keyframe — injected lazily on first click
   ───────────────────────────────────────────────────────── */
let _rippleInjected = false;

function ensureRippleStyle() {
  if (_rippleInjected || typeof document === 'undefined') return;
  _rippleInjected = true;
  const id = '__ds-ripple-style';
  if (document.getElementById(id)) return;
  const style = document.createElement('style');
  style.id = id;
  style.textContent = `
    @keyframes ripple-expand {
      to { transform: translate(-50%, -50%) scale(1); opacity: 0; }
    }
  `;
  document.head.appendChild(style);
}

/* ─────────────────────────────────────────────────────────
   Button
   ───────────────────────────────────────────────────────── */
export function Button({
  children,
  variant   = 'secondary', // 'primary'|'secondary'|'ghost'|'danger'|'success'
  size      = 'md',        // 'xs'|'sm'|'md'|'lg'|'icon'
  loading   = false,
  disabled  = false,
  leftIcon  = null,
  rightIcon = null,
  href      = null,        // renders as <a> if provided
  type      = 'button',
  onClick,
  className = '',
  style     = {},
  ...rest
}) {
  const [ripple, setRipple] = useState(null);

  const handleClick = (e) => {
    ensureRippleStyle(); // inject CSS lazily on first interaction

    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setRipple({ x, y });
    setTimeout(() => setRipple(null), 600);

    onClick?.(e);
  };

  const classNames = [
    'btn',
    `btn-${variant}`,
    size !== 'md' ? `btn-${size}` : '',
    loading ? 'is-loading' : '',
    className,
  ].filter(Boolean).join(' ');

  const content = (
    <>
      {/* Ripple */}
      {ripple && (
        <span
          aria-hidden="true"
          style={{
            position: 'absolute',
            left: ripple.x,
            top:  ripple.y,
            transform: 'translate(-50%, -50%) scale(0)',
            width: '200px',
            height: '200px',
            borderRadius: '50%',
            background: 'rgba(255,255,255,0.12)',
            animation: 'ripple-expand 0.6s ease-out forwards',
            pointerEvents: 'none',
          }}
        />
      )}

      {/* Left icon */}
      {leftIcon && !loading && (
        <span className="btn-icon-left" aria-hidden="true" style={{ lineHeight: 1 }}>
          {leftIcon}
        </span>
      )}

      {/* Label */}
      <span className="btn-text">{children}</span>

      {/* Right icon */}
      {rightIcon && !loading && (
        <span className="btn-icon-right" aria-hidden="true" style={{ lineHeight: 1 }}>
          {rightIcon}
        </span>
      )}
    </>
  );

  if (href) {
    return (
      <a href={href} className={classNames} style={style} {...rest}>
        {content}
      </a>
    );
  }

  return (
    <button
      type={type}
      className={classNames}
      disabled={disabled || loading}
      onClick={handleClick}
      style={style}
      aria-busy={loading}
      aria-disabled={disabled || loading}
      {...rest}
    >
      {content}
    </button>
  );
}

/* ─────────────────────────────────────────────────────────
   ButtonGroup — 여러 버튼을 묶는 래퍼
   ───────────────────────────────────────────────────────── */
export function ButtonGroup({ children, gap = 'var(--space-2)', style = {} }) {
  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap,
        flexWrap: 'wrap',
        ...style,
      }}
    >
      {children}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────
   IconButton — 아이콘 전용 편의 래퍼
   ───────────────────────────────────────────────────────── */
export function IconButton({ icon, label, variant = 'ghost', size = 'icon', ...rest }) {
  return (
    <Button
      variant={variant}
      size={size}
      aria-label={label}
      title={label}
      {...rest}
    >
      <span aria-hidden="true">{icon}</span>
    </Button>
  );
}
