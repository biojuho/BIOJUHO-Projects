import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, RefreshCw, ServerCog, XCircle } from 'lucide-react';
import client from '../services/api';
import { useLocale } from '../contexts/LocaleContext';
import { formatSupportError } from '../lib/support';
import GlassCard from './ui/GlassCard';
import { Badge } from './ui/Badge';

const CHECK_FALLBACKS = {
  api: 'API',
  auth: 'Authentication',
  vector_store: 'Vector index',
  llm: 'AI provider',
  postgres: 'PostgreSQL',
  supabase: 'Supabase',
  redis: 'Redis',
  rabbitmq: 'RabbitMQ',
  ipfs: 'IPFS',
  web3: 'Web3',
  grobid: 'GROBID',
};

function safeText(t, key, fallback, values) {
  const translated = t(key, values);
  if (translated !== key) return translated;
  if (!values) return fallback;
  return fallback.replace(/\{(\w+)\}/g, (match, name) => (
    Object.prototype.hasOwnProperty.call(values, name) ? String(values[name]) : match
  ));
}

function getStatusMeta(status) {
  if (status === 'pass') {
    return {
      icon: CheckCircle2,
      badge: 'success',
      iconClass: 'text-success',
      rowClass: 'border-success/20 bg-success/10',
    };
  }

  if (status === 'fail') {
    return {
      icon: XCircle,
      badge: 'error',
      iconClass: 'text-error-dark',
      rowClass: 'border-error/20 bg-error/10',
    };
  }

  return {
    icon: AlertTriangle,
    badge: 'warning',
    iconClass: 'text-warning-dark',
    rowClass: 'border-warning/20 bg-warning/10',
  };
}

function getReadinessBadge(status) {
  if (status === 'ready') return 'success';
  if (status === 'blocked') return 'error';
  if (status === 'unavailable') return 'error';
  return 'warning';
}

function formatCheckedAt(value, locale) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString(locale);
}

export default function ProductReadinessPanel() {
  const { locale, t } = useLocale();
  const [readiness, setReadiness] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchReadiness = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await client.get('/ready', { timeout: 10_000 });
      setReadiness(response.data);
    } catch (nextError) {
      setReadiness({
        status: 'unavailable',
        summary: { ready_count: 0, total: 0, required_ready_count: 0, required_total: 0 },
        checks: [],
      });
      setError(nextError);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchReadiness();
  }, [fetchReadiness]);

  const checks = Array.isArray(readiness?.checks) ? readiness.checks : [];
  const summary = readiness?.summary ?? {};
  const total = summary.total || checks.length || 0;
  const readyCount = summary.ready_count || checks.filter((check) => check.status === 'pass').length;
  const requiredTotal = summary.required_total || checks.filter((check) => check.required).length || 0;
  const requiredReady = summary.required_ready_count || checks.filter((check) => check.required && check.status === 'pass').length;
  const progress = total > 0 ? Math.round((readyCount / total) * 100) : 0;
  const status = readiness?.status || 'degraded';
  const checkedAt = useMemo(() => formatCheckedAt(readiness?.checked_at, locale), [readiness?.checked_at, locale]);

  const visibleChecks = loading && checks.length === 0
    ? ['api', 'auth', 'vector_store', 'llm'].map((id) => ({ id, status: 'warn', required: true }))
    : checks;

  return (
    <GlassCard className="p-7">
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex items-start gap-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-white text-primary shadow-clay-soft">
            <ServerCog className="h-5 w-5" />
          </div>
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-ink-soft">
              {safeText(t, 'readiness.eyebrow', 'Product Operations')}
            </p>
            <h2 className="mt-2 font-display text-2xl font-semibold text-ink">
              {safeText(t, 'readiness.title', 'Launch readiness')}
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-7 text-ink-muted">
              {safeText(t, 'readiness.subtitle', 'Confirm the core services needed for a production-grade research marketplace.')}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={getReadinessBadge(status)}>
            {safeText(t, `readiness.status.${status}`, status)}
          </Badge>
          <button
            type="button"
            onClick={fetchReadiness}
            disabled={loading}
            className="clay-button h-10 !px-3 text-xs"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            {safeText(t, 'readiness.refresh', 'Refresh')}
          </button>
        </div>
      </div>

      <div className="mb-6 grid gap-4 lg:grid-cols-[1.15fr,0.85fr]">
        <div className="clay-panel-pressed rounded-[1.6rem] p-5">
          <div className="mb-3 flex items-center justify-between gap-3">
            <span className="text-sm font-semibold text-ink">
              {safeText(t, 'readiness.overallProgress', 'Overall readiness')}
            </span>
            <span className="font-mono text-sm font-semibold text-ink">{progress}%</span>
          </div>
          <div className="h-3 overflow-hidden rounded-full bg-white/65">
            <div
              className="h-full rounded-full bg-gradient-to-r from-primary to-success transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="mt-3 flex flex-wrap gap-3 text-xs font-semibold text-ink-muted">
            <span>{safeText(t, 'readiness.readySummary', '{ready}/{total} checks ready', { ready: readyCount, total })}</span>
            <span>{safeText(t, 'readiness.requiredSummary', '{ready}/{total} required ready', { ready: requiredReady, total: requiredTotal })}</span>
          </div>
        </div>

        <div className="clay-panel-pressed rounded-[1.6rem] p-5">
          <p className="text-sm font-semibold text-ink">
            {safeText(t, 'readiness.operatorNoteTitle', 'Operator note')}
          </p>
          <p className="mt-2 text-sm leading-7 text-ink-muted">
            {error
              ? formatSupportError(error, safeText(t, 'readiness.apiUnavailable', 'Readiness API is unavailable. Check backend connectivity before demo or launch.'))
              : safeText(t, `readiness.note.${status}`, 'Review warnings before production launch.')}
          </p>
          {checkedAt && (
            <p className="mt-3 text-xs font-semibold text-ink-soft">
              {safeText(t, 'readiness.updatedAt', 'Updated {time}', { time: checkedAt })}
            </p>
          )}
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {visibleChecks.map((check) => {
          const meta = getStatusMeta(check.status);
          const Icon = meta.icon;
          const fallbackLabel = CHECK_FALLBACKS[check.id] || check.id;
          const statusText = safeText(t, `readiness.checkStatus.${check.status}`, check.status);
          const detailKey = `readiness.detail.${check.id}.${check.status}`;

          return (
            <div key={check.id} className={`rounded-[1.4rem] border p-4 ${meta.rowClass}`}>
              <div className="mb-3 flex items-start justify-between gap-3">
                <div className="flex min-w-0 items-center gap-3">
                  <Icon className={`h-5 w-5 shrink-0 ${meta.iconClass}`} />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-ink">
                      {safeText(t, `readiness.check.${check.id}`, fallbackLabel)}
                    </p>
                    <p className="text-xs font-semibold text-ink-soft">
                      {check.required
                        ? safeText(t, 'readiness.required', 'Required')
                        : safeText(t, 'readiness.optional', 'Optional')}
                    </p>
                  </div>
                </div>
                <Badge variant={meta.badge}>{statusText}</Badge>
              </div>
              <p className="text-sm leading-6 text-ink-muted">
                {safeText(t, detailKey, safeText(t, `readiness.detail.default.${check.status}`, statusText))}
                {typeof check.metric === 'number' && (
                  <span className="ml-1 font-semibold text-ink">
                    {safeText(t, 'readiness.metricDocuments', '({count} docs)', { count: check.metric })}
                  </span>
                )}
              </p>
              {check.remediation && check.status !== 'pass' && (
                <p className="mt-2 text-xs font-semibold leading-5 text-ink">
                  {check.remediation}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </GlassCard>
  );
}
