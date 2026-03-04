/**
 * ErrorBoundary Component
 * Uses react-error-boundary for declarative error handling with retry support.
 */
import { ErrorBoundary as ReactErrorBoundary } from 'react-error-boundary';
import { AlertTriangle, RotateCcw, Home } from 'lucide-react';

function ErrorFallback({ error, resetErrorBoundary }) {
  return (
    <div className="min-h-screen bg-[#040811] flex items-center justify-center px-4">
      <div className="max-w-md w-full text-center">
        {/* Icon */}
        <div className="mx-auto mb-6 w-16 h-16 rounded-2xl flex items-center justify-center bg-red-500/10 border border-red-500/20">
          <AlertTriangle className="w-8 h-8 text-red-400" />
        </div>

        {/* Heading */}
        <h1 className="font-display text-2xl font-bold text-white mb-3">
          Something went wrong
        </h1>

        {/* Error message */}
        <p className="text-white/50 text-sm mb-2">
          An unexpected error occurred. You can try again or return to the dashboard.
        </p>
        {error?.message && (
          <pre className="text-xs text-red-400/70 bg-red-500/5 border border-red-500/10 rounded-xl p-3 mb-6 max-h-24 overflow-auto text-left whitespace-pre-wrap break-words">
            {error.message}
          </pre>
        )}

        {/* Action buttons */}
        <div className="flex items-center justify-center gap-3">
          <button
            onClick={resetErrorBoundary}
            className="flex items-center gap-2 px-5 py-2.5 bg-primary/10 text-primary border border-primary/20 rounded-xl hover:bg-primary/20 transition-colors text-sm font-medium"
          >
            <RotateCcw className="w-4 h-4" />
            Try Again
          </button>
          <button
            onClick={() => {
              window.location.href = '/dashboard';
            }}
            className="flex items-center gap-2 px-5 py-2.5 bg-white/[0.04] text-white/70 border border-white/[0.08] rounded-xl hover:bg-white/[0.08] transition-colors text-sm font-medium"
          >
            <Home className="w-4 h-4" />
            Go to Dashboard
          </button>
        </div>
      </div>
    </div>
  );
}

function handleErrorLog(error, info) {
  // Log to console in development; could send to monitoring service in production
  console.error('ErrorBoundary caught an error:', error);
  console.error('Component stack:', info?.componentStack);
}

/**
 * AppErrorBoundary - wraps children with react-error-boundary.
 * Usage: <AppErrorBoundary><App /></AppErrorBoundary>
 */
export default function AppErrorBoundary({ children }) {
  return (
    <ReactErrorBoundary
      FallbackComponent={ErrorFallback}
      onError={handleErrorLog}
      onReset={() => {
        // Reset any app-level state on retry if needed
      }}
    >
      {children}
    </ReactErrorBoundary>
  );
}

// Also export the fallback for use in granular error boundaries
export { ErrorFallback };
