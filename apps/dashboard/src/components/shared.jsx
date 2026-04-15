import { Button } from './Button.jsx'

export function Loading() {
  return <div className="loading"><div className="spinner" /> 데이터 로딩 중...</div>
}

export function PanelState({ error, onRetry }) {
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

export function ChartLoading({ height = 220 }) {
  return (
    <div className="loading" style={{ height, fontSize: '0.75rem' }}>
      <div className="spinner" /> Loading chart...
    </div>
  )
}
