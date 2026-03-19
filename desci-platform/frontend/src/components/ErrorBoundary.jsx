import { ErrorBoundary as ReactErrorBoundary } from 'react-error-boundary';
import { AlertTriangle, RotateCcw, Home } from 'lucide-react';
import { formatMessage } from '../i18n/messages';
import { getStoredLocale } from '../contexts/LocaleContext';

function t(key) {
  return formatMessage(getStoredLocale(), key);
}

function ErrorFallback({ error, resetErrorBoundary }) {
  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="glass-card max-w-lg p-10 text-center">
        <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-error/12 text-error shadow-clay-soft">
          <AlertTriangle className="h-8 w-8" />
        </div>
        <h1 className="mb-3 font-display text-3xl font-semibold text-ink">{t('errors.title')}</h1>
        <p className="mb-4 text-sm leading-7 text-ink-muted">{t('errors.body')}</p>
        {error?.message && (
          <pre className="clay-panel-pressed mb-6 max-h-28 overflow-auto rounded-[1.5rem] p-4 text-left text-xs text-error-dark whitespace-pre-wrap break-words">
            {error.message}
          </pre>
        )}
        <div className="flex flex-wrap items-center justify-center gap-3">
          <button onClick={resetErrorBoundary} className="clay-button clay-button-primary text-white">
            <RotateCcw className="h-4 w-4" />
            {t('errors.retry')}
          </button>
          <button
            onClick={() => {
              window.location.href = '/dashboard';
            }}
            className="clay-button"
          >
            <Home className="h-4 w-4" />
            {t('errors.goHome')}
          </button>
        </div>
      </div>
    </div>
  );
}

function handleErrorLog(error, info) {
  console.error('ErrorBoundary caught an error:', error);
  console.error('Component stack:', info?.componentStack);
}

export default function AppErrorBoundary({ children }) {
  return (
    <ReactErrorBoundary FallbackComponent={ErrorFallback} onError={handleErrorLog}>
      {children}
    </ReactErrorBoundary>
  );
}

export { ErrorFallback };
