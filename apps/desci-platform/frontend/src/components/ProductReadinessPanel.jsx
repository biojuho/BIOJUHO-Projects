import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, Check, CheckCircle2, Copy, RefreshCw, ServerCog, XCircle } from 'lucide-react';
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
  stripe: 'Stripe billing',
  stripe_return_url: 'Stripe return URL',
  stripe_portal: 'Stripe portal configuration',
  cors: 'CORS origins',
  postgres: 'PostgreSQL',
  supabase: 'Supabase',
  redis: 'Redis',
  rabbitmq: 'RabbitMQ',
  ipfs: 'IPFS',
  web3: 'Web3',
  grobid: 'GROBID',
};

const ALL_ACTIONS_ID = '__all__';
const ENV_HANDOFF_ID = '__env_handoff__';
const ENV_HANDOFF_PLACEHOLDER = '<set-secure-value>';

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

function getLaunchDecisionBadge(decision) {
  if (decision === 'go') return 'success';
  if (decision === 'no-go' || decision === 'unavailable') return 'error';
  return 'warning';
}

function formatCheckedAt(value, locale) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString(locale);
}

function formatLaunchActionPayload(action) {
  return [
    `Launch action: ${action.label}`,
    `Priority: ${action.required ? 'required' : 'optional'}`,
    `Status: ${action.status}`,
    `Remediation: ${action.remediation}`,
    action.requiredEnv.length > 0 ? `Required env: ${action.requiredEnv.join(', ')}` : null,
  ].filter(Boolean).join('\n');
}

function buildLaunchEnvHandoff(actions) {
  const required = uniqueStrings(actions
    .filter((action) => action.required)
    .flatMap((action) => action.requiredEnv));
  const requiredSet = new Set(required);
  const optional = uniqueStrings(actions
    .filter((action) => !action.required)
    .flatMap((action) => action.requiredEnv))
    .filter((envKey) => !requiredSet.has(envKey));

  return {
    required,
    optional,
    count: required.length + optional.length,
  };
}

function formatLaunchEnvHandoffPayload(handoff) {
  const lines = [
    '# DSCI launch env handoff',
    '# Replace placeholders in the target secret manager or runtime environment.',
  ];

  if (handoff.required.length > 0) {
    lines.push('', '# Required before release');
    handoff.required.forEach((envKey) => {
      lines.push(`${envKey}=${ENV_HANDOFF_PLACEHOLDER}`);
    });
  }

  if (handoff.optional.length > 0) {
    lines.push('', '# Optional launch hardening');
    handoff.optional.forEach((envKey) => {
      lines.push(`${envKey}=${ENV_HANDOFF_PLACEHOLDER}`);
    });
  }

  return lines.join('\n');
}

function formatReadinessError(error, fallback) {
  if (!error?.response) return fallback;
  return formatSupportError(error, fallback);
}

function unavailableReadinessPayload() {
  return {
    status: 'unavailable',
    summary: { ready_count: 0, total: 0, required_ready_count: 0, required_total: 0 },
    checks: [],
  };
}

function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function listEquals(left, right) {
  if (!Array.isArray(left) || !Array.isArray(right)) return false;
  if (left.length !== right.length) return false;
  return left.every((value, index) => value === right[index]);
}

function uniqueStrings(values) {
  if (!Array.isArray(values)) return [];

  const seen = new Set();
  const result = [];
  values.forEach((value) => {
    if (typeof value !== 'string') return;
    const normalized = value.trim();
    if (!normalized || seen.has(normalized)) return;
    seen.add(normalized);
    result.push(normalized);
  });
  return result;
}

function stringSetEquals(left, right) {
  const leftValues = uniqueStrings(left);
  const rightValues = uniqueStrings(right);
  if (leftValues.length !== rightValues.length) return false;

  const rightSet = new Set(rightValues);
  return leftValues.every((value) => rightSet.has(value));
}

function readinessActionChecks(readiness) {
  if (!Array.isArray(readiness?.checks)) return [];

  return readiness.checks.filter((check) => (
    isObject(check)
    && (check.status === 'warn' || (check.required && check.status === 'fail'))
  ));
}

function actionIdsFromItems(items) {
  return uniqueStrings(items.map((item) => item?.id));
}

function requiredEnvFromItems(items) {
  return uniqueStrings(items.flatMap((item) => (
    Array.isArray(item?.required_env) ? item.required_env : []
  )));
}

function readinessLaunchDrift(readiness, launchControl) {
  if (!isObject(readiness) || !isObject(launchControl)) return [];

  const warnings = [];
  if (readiness.status !== launchControl.readiness_status) {
    warnings.push('status');
  }

  const readySummary = readiness.summary;
  const launchSummary = launchControl.summary;
  if (isObject(readySummary) && isObject(launchSummary)) {
    const fields = ['ready_count', 'total', 'required_ready_count', 'required_total'];
    if (fields.some((field) => readySummary[field] !== launchSummary[field])) {
      warnings.push('summary');
    }
  }

  if (
    Array.isArray(readiness.launch_blockers)
    && Array.isArray(launchControl.launch_blockers)
    && !listEquals(readiness.launch_blockers, launchControl.launch_blockers)
  ) {
    warnings.push('blockers');
  }

  if (Array.isArray(readiness.checks) && Array.isArray(launchControl.next_actions)) {
    const readyActions = readinessActionChecks(readiness);
    const launchActions = launchControl.next_actions.filter(isObject);

    if (!stringSetEquals(actionIdsFromItems(readyActions), actionIdsFromItems(launchActions))) {
      warnings.push('actions');
    }

    if (!stringSetEquals(requiredEnvFromItems(readyActions), requiredEnvFromItems(launchActions))) {
      warnings.push('requiredEnv');
    }
  }

  return warnings;
}

function web3StatusText(ok, passText, warnText) {
  return ok ? passText : warnText;
}

function buildWeb3Triage(check) {
  if (!isObject(check?.details)) return null;
  const details = check.details;
  const contracts = isObject(details.contracts) ? details.contracts : {};
  const contractEntries = Object.entries(contracts)
    .filter(([key, value]) => typeof key === 'string' && typeof value === 'boolean')
    .map(([key, value]) => ({ key, ok: value }));
  const contractCount = Number.isInteger(details.contract_count)
    ? details.contract_count
    : contractEntries.filter((entry) => entry.ok).length;
  const rpcReady = details.rpc_configured === true && details.rpc_public_https === true;
  const mockEnabled = details.mock_mode_enabled === true;
  const mockAllowed = details.mock_mode_allowed === true;

  return {
    status: check.status || 'warn',
    rpcReady,
    rpcText: web3StatusText(
      rpcReady,
      'Public HTTPS RPC configured',
      details.rpc_configured === true ? 'RPC configured, not public HTTPS' : 'WEB3_RPC_URL not configured',
    ),
    contractReady: contractCount > 0,
    contractText: `${contractCount} valid contract env ${contractCount === 1 ? 'value' : 'values'}`,
    contractEntries,
    mockReady: !mockEnabled || mockAllowed,
    mockText: !mockEnabled
      ? 'MOCK_MODE off'
      : web3StatusText(mockAllowed, 'MOCK_MODE allowed for local runtime', 'MOCK_MODE enabled in production path'),
  };
}

async function fetchProductReadiness({ signal }) {
  const response = await client.get('/ready', {
    timeout: 10_000,
    suppressErrorLog: true,
    signal,
  });
  return response.data;
}

async function fetchLaunchControl({ signal }) {
  const response = await client.get('/launch', {
    timeout: 10_000,
    suppressErrorLog: true,
    signal,
  });
  return response.data;
}

export default function ProductReadinessPanel() {
  const { locale, t } = useLocale();
  const [copiedActionId, setCopiedActionId] = useState(null);
  const [copyFeedback, setCopyFeedback] = useState(null);
  const copyFeedbackTimerRef = useRef(null);

  const {
    data: readinessData,
    error,
    isLoading: readinessLoading,
    isFetching: readinessFetching,
    refetch: refetchReadiness,
  } = useQuery({
    queryKey: ['product-readiness', 'ready'],
    queryFn: fetchProductReadiness,
    retry: false,
    staleTime: 10_000,
    gcTime: 60_000,
  });

  const {
    data: launchData,
    error: launchError,
    isLoading: launchLoading,
    isFetching: launchFetching,
    refetch: refetchLaunch,
  } = useQuery({
    queryKey: ['product-readiness', 'launch'],
    queryFn: fetchLaunchControl,
    retry: false,
    staleTime: 10_000,
    gcTime: 60_000,
  });

  const clearCopyFeedbackTimer = useCallback(() => {
    if (copyFeedbackTimerRef.current) {
      window.clearTimeout(copyFeedbackTimerRef.current);
      copyFeedbackTimerRef.current = null;
    }
  }, []);

  const showCopyFeedback = useCallback((kind, message, actionId = null) => {
    clearCopyFeedbackTimer();
    setCopiedActionId(kind === 'success' ? actionId : null);
    setCopyFeedback({ kind, message });
    copyFeedbackTimerRef.current = window.setTimeout(() => {
      setCopiedActionId(null);
      setCopyFeedback(null);
      copyFeedbackTimerRef.current = null;
    }, 3000);
  }, [clearCopyFeedbackTimer]);

  const fetchReadiness = useCallback(async () => {
    await Promise.all([refetchReadiness(), refetchLaunch()]);
  }, [refetchLaunch, refetchReadiness]);

  useEffect(() => () => {
    clearCopyFeedbackTimer();
  }, [clearCopyFeedbackTimer]);

  const readiness = isObject(readinessData) ? readinessData : unavailableReadinessPayload();
  const launchControl = isObject(launchData) ? launchData : null;
  const loading = readinessLoading || launchLoading || readinessFetching || launchFetching;
  const checks = useMemo(
    () => (Array.isArray(readiness?.checks) ? readiness.checks : []),
    [readiness],
  );
  const summary = readiness?.summary ?? {};
  const total = summary.total || checks.length || 0;
  const readyCount = summary.ready_count || checks.filter((check) => check.status === 'pass').length;
  const requiredTotal = summary.required_total || checks.filter((check) => check.required).length || 0;
  const requiredReady = summary.required_ready_count || checks.filter((check) => check.required && check.status === 'pass').length;
  const progress = total > 0 ? Math.round((readyCount / total) * 100) : 0;
  const status = readiness?.status || 'degraded';
  const checkedAt = useMemo(() => formatCheckedAt(readiness?.checked_at, locale), [readiness?.checked_at, locale]);
  const launchDecision = launchError
    ? 'unavailable'
    : launchControl?.release_decision || 'syncing';
  const launchPhase = launchControl?.operator_phase || (launchError ? 'unavailable' : 'syncing');
  const requiredScore = launchControl?.score?.required_percent;
  const overallScore = launchControl?.score?.overall_percent;
  const launchDriftWarnings = useMemo(
    () => readinessLaunchDrift(readiness, launchControl),
    [launchControl, readiness],
  );
  const web3Triage = useMemo(
    () => buildWeb3Triage(checks.find((check) => check.id === 'web3')),
    [checks],
  );
  const launchActions = useMemo(() => (
    (
      Array.isArray(launchControl?.next_actions)
        ? launchControl.next_actions
        : checks.filter((check) => check.status !== 'pass' && (check.required || check.remediation))
    )
      .map((action, index) => {
        const id = action.id || `action-${index + 1}`;
        const statusText = action.status || (action.required ? 'fail' : 'warn');
        return {
          id,
          required: Boolean(action.required),
          status: statusText,
          label: CHECK_FALLBACKS[id] || id,
          remediation: action.remediation || safeText(t, `readiness.detail.default.${statusText}`, statusText),
          requiredEnv: Array.isArray(action.required_env) ? action.required_env.filter(Boolean) : [],
        };
      })
  ), [checks, launchControl, t]);
  const launchEnvHandoff = useMemo(() => buildLaunchEnvHandoff(launchActions), [launchActions]);
  const copyLaunchAction = useCallback(async (action) => {
    const label = safeText(t, `readiness.check.${action.id}`, action.label);
    try {
      await navigator.clipboard.writeText(formatLaunchActionPayload(action));
      showCopyFeedback(
        'success',
        safeText(t, 'readiness.copyFeedback.success', 'Copied {label} launch action.', { label }),
        action.id,
      );
    } catch {
      showCopyFeedback(
        'error',
        safeText(t, 'readiness.copyFeedback.error', 'Could not copy {label}. Use the visible remediation and env list.', { label }),
      );
    }
  }, [showCopyFeedback, t]);
  const copyAllLaunchActions = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(launchActions.map(formatLaunchActionPayload).join('\n\n---\n\n'));
      showCopyFeedback(
        'success',
        safeText(t, 'readiness.copyFeedback.successAll', 'Copied {count} launch actions.', { count: launchActions.length }),
        ALL_ACTIONS_ID,
      );
    } catch {
      showCopyFeedback(
        'error',
        safeText(t, 'readiness.copyFeedback.errorAll', 'Could not copy launch actions. Use the visible remediation and env list.'),
      );
    }
  }, [launchActions, showCopyFeedback, t]);
  const copyLaunchEnvHandoff = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(formatLaunchEnvHandoffPayload(launchEnvHandoff));
      showCopyFeedback(
        'success',
        safeText(t, 'readiness.copyFeedback.envHandoffSuccess', 'Copied launch env handoff.'),
        ENV_HANDOFF_ID,
      );
    } catch {
      showCopyFeedback(
        'error',
        safeText(t, 'readiness.copyFeedback.envHandoffError', 'Could not copy launch env handoff. Use the visible placeholder env list.'),
      );
    }
  }, [launchEnvHandoff, showCopyFeedback, t]);

  const visibleChecks = loading && checks.length === 0
    ? ['api', 'auth', 'vector_store', 'llm'].map((id) => ({ id, status: 'warn', required: true }))
    : checks;

  return (
    <div data-testid="product-readiness-panel">
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
          <Badge variant={getReadinessBadge(status)} data-testid="product-readiness-status">
            {safeText(t, `readiness.status.${status}`, status)}
          </Badge>
          <button
            type="button"
            onClick={fetchReadiness}
            disabled={loading}
            data-testid="product-readiness-refresh"
            className="clay-button h-10 !px-3 text-xs"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            {safeText(t, 'readiness.refresh', 'Refresh')}
          </button>
        </div>
      </div>

      <div className="mb-6 grid gap-4 lg:grid-cols-3">
        <div className="clay-panel-pressed rounded-[1.6rem] p-5">
          <div className="mb-3 flex items-center justify-between gap-3">
            <span className="text-sm font-semibold text-ink">
              {safeText(t, 'readiness.overallProgress', 'Overall readiness')}
            </span>
            <span className="font-mono text-sm font-semibold text-ink" data-testid="product-readiness-progress">{progress}%</span>
          </div>
          <div className="h-3 overflow-hidden rounded-full bg-white/65">
            <div
              className="h-full rounded-full bg-gradient-to-r from-primary to-success transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="mt-3 flex flex-wrap gap-3 text-xs font-semibold text-ink-muted">
            <span data-testid="product-readiness-ready-summary">
              {safeText(t, 'readiness.readySummary', '{ready}/{total} checks ready', { ready: readyCount, total })}
            </span>
            <span data-testid="product-readiness-required-summary">
              {safeText(t, 'readiness.requiredSummary', '{ready}/{total} required ready', { ready: requiredReady, total: requiredTotal })}
            </span>
          </div>
        </div>

        <div className="clay-panel-pressed rounded-[1.6rem] p-5">
          <p className="text-sm font-semibold text-ink">
            {safeText(t, 'readiness.operatorNoteTitle', 'Operator note')}
          </p>
          <p className="mt-2 text-sm leading-7 text-ink-muted">
            {error
              ? formatReadinessError(error, safeText(t, 'readiness.apiUnavailable', 'Readiness API is unavailable. Check backend connectivity before demo or launch.'))
              : safeText(t, `readiness.note.${status}`, 'Review warnings before production launch.')}
          </p>
          {checkedAt && (
            <p className="mt-3 text-xs font-semibold text-ink-soft">
              {safeText(t, 'readiness.updatedAt', 'Updated {time}', { time: checkedAt })}
            </p>
          )}
        </div>

        <div className="clay-panel-pressed rounded-[1.6rem] p-5" data-testid="product-readiness-launch-control">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <span className="text-sm font-semibold text-ink">
              {safeText(t, 'readiness.launchControlTitle', 'Launch control')}
            </span>
            <Badge variant={getLaunchDecisionBadge(launchDecision)} data-testid="product-readiness-release-decision">
              {safeText(t, `readiness.launchDecision.${launchDecision}`, launchDecision)}
            </Badge>
          </div>
          <div className="grid gap-2 text-xs font-semibold text-ink-muted">
            <p data-testid="product-readiness-operator-phase">
              {safeText(t, 'readiness.operatorPhaseLabel', 'Phase')}: {safeText(t, `readiness.operatorPhase.${launchPhase}`, launchPhase)}
            </p>
            <p data-testid="product-readiness-launch-score">
              {safeText(t, 'readiness.requiredScoreLabel', 'Required score')}: {
                typeof requiredScore === 'number' ? `${requiredScore}%` : safeText(t, 'readiness.launchControlSyncing', 'Syncing')
              }
              {typeof overallScore === 'number' && (
                <span className="ml-2 text-ink-soft">
                  {safeText(t, 'readiness.overallScoreLabel', 'Overall')} {overallScore}%
                </span>
              )}
            </p>
          </div>
          {launchError && (
            <p className="mt-3 text-xs font-semibold leading-5 text-error-dark" role="alert">
              {formatReadinessError(
                launchError,
                safeText(t, 'readiness.launchControlUnavailable', 'Launch control is unavailable. Check /launch before operator handoff.'),
              )}
            </p>
          )}
        </div>
      </div>

      {launchDriftWarnings.length > 0 && (
        <div
          className="mb-6 rounded-[1.2rem] border border-error/25 bg-error/10 p-4 text-sm font-semibold text-error-dark"
          data-testid="product-readiness-launch-drift"
          role="alert"
        >
          <p>{safeText(t, 'readiness.launchDriftTitle', 'Launch control does not match readiness evidence.')}</p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {launchDriftWarnings.map((warning) => (
              <li key={warning}>
                {safeText(t, `readiness.launchDrift.${warning}`, warning)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {web3Triage && (
        <div
          className="mb-6 rounded-[1.2rem] border border-primary/15 bg-white/70 p-5"
          data-testid="product-readiness-web3-triage"
        >
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-ink">
                {safeText(t, 'readiness.web3TriageTitle', 'Web3 launch triage')}
              </p>
              <p className="mt-1 text-xs font-semibold text-ink-muted">
                {safeText(t, 'readiness.web3TriageSubtitle', 'Non-secret RPC, contract, and mock-mode readiness from /ready.')}
              </p>
            </div>
            <Badge variant={getStatusMeta(web3Triage.status).badge}>
              {safeText(t, `readiness.checkStatus.${web3Triage.status}`, web3Triage.status)}
            </Badge>
          </div>
          <div className="grid gap-3 lg:grid-cols-3">
            <div className="rounded-[0.8rem] border border-white/70 bg-white/75 p-4" data-testid="product-readiness-web3-rpc">
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-ink-soft">
                {safeText(t, 'readiness.web3RpcLabel', 'RPC')}
              </p>
              <p className={`mt-2 text-sm font-semibold ${web3Triage.rpcReady ? 'text-success' : 'text-warning-dark'}`}>
                {safeText(t, `readiness.web3Rpc.${web3Triage.rpcReady ? 'ready' : 'review'}`, web3Triage.rpcText)}
              </p>
            </div>
            <div className="rounded-[0.8rem] border border-white/70 bg-white/75 p-4" data-testid="product-readiness-web3-contracts">
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-ink-soft">
                {safeText(t, 'readiness.web3ContractsLabel', 'Contracts')}
              </p>
              <p className={`mt-2 text-sm font-semibold ${web3Triage.contractReady ? 'text-success' : 'text-warning-dark'}`}>
                {web3Triage.contractText}
              </p>
              {web3Triage.contractEntries.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {web3Triage.contractEntries.map((entry) => (
                    <span
                      key={entry.key}
                      data-testid={`product-readiness-web3-contract-${entry.key}`}
                      className={`rounded-full px-2.5 py-1 font-mono text-[11px] font-semibold ${
                        entry.ok ? 'bg-success/10 text-success' : 'bg-warning/10 text-warning-dark'
                      }`}
                    >
                      {entry.key}: {entry.ok ? 'valid' : 'missing'}
                    </span>
                  ))}
                </div>
              )}
            </div>
            <div className="rounded-[0.8rem] border border-white/70 bg-white/75 p-4" data-testid="product-readiness-web3-mock">
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-ink-soft">
                {safeText(t, 'readiness.web3MockLabel', 'Mock mode')}
              </p>
              <p className={`mt-2 text-sm font-semibold ${web3Triage.mockReady ? 'text-success' : 'text-error-dark'}`}>
                {safeText(t, `readiness.web3Mock.${web3Triage.mockReady ? 'ready' : 'blocked'}`, web3Triage.mockText)}
              </p>
            </div>
          </div>
        </div>
      )}

      {launchActions.length > 0 && (
        <div
          className="mb-6 rounded-[1.2rem] border border-warning/25 bg-warning/10 p-5"
          data-testid="product-readiness-next-actions"
        >
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-ink">
                {safeText(t, 'readiness.nextActionsTitle', 'Launch action queue')}
              </p>
              <p className="mt-1 text-xs font-semibold text-ink-muted">
                {safeText(t, 'readiness.nextActionsSubtitle', '{count} action(s) need operator attention', {
                  count: launchActions.length,
                })}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={status === 'blocked' ? 'error' : 'warning'}>
                {safeText(t, 'readiness.nextActionsBadge', 'Action required')}
              </Badge>
              <button
                type="button"
                onClick={copyAllLaunchActions}
                data-testid="product-readiness-next-actions-copy-all"
                aria-label={`Copy all ${launchActions.length} launch actions`}
                className="inline-flex h-9 items-center gap-2 rounded-full border border-white/70 bg-white/80 px-3 text-xs font-semibold text-ink shadow-clay-soft transition hover:bg-white"
              >
                {copiedActionId === ALL_ACTIONS_ID ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                {copiedActionId === ALL_ACTIONS_ID
                  ? safeText(t, 'common.copied', 'Copied')
                  : safeText(t, 'common.copyAll', 'Copy all')}
              </button>
            </div>
          </div>
          {copyFeedback && (
            <p
              data-testid="product-readiness-copy-feedback"
              role={copyFeedback.kind === 'error' ? 'alert' : 'status'}
              aria-live={copyFeedback.kind === 'error' ? 'assertive' : 'polite'}
              className={`mb-4 rounded-full border px-3 py-2 text-xs font-semibold ${
                copyFeedback.kind === 'error'
                  ? 'border-error/25 bg-error/10 text-error-dark'
                  : 'border-success/25 bg-success/10 text-success'
              }`}
            >
              {copyFeedback.message}
            </p>
          )}
          {launchEnvHandoff.count > 0 && (
            <div
              className="mb-4 rounded-[0.9rem] border border-white/70 bg-white/75 p-4"
              data-testid="product-readiness-env-handoff"
            >
              <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.16em] text-ink-soft">
                    {safeText(t, 'readiness.envHandoffTitle', 'Launch env handoff')}
                  </p>
                  <p className="mt-1 text-sm font-semibold text-ink">
                    {safeText(t, 'readiness.envHandoffSubtitle', '{count} placeholder env value(s)', {
                      count: launchEnvHandoff.count,
                    })}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={copyLaunchEnvHandoff}
                  data-testid="product-readiness-env-handoff-copy"
                  aria-label="Copy launch env handoff"
                  className="inline-flex h-9 items-center gap-2 rounded-full border border-white/70 bg-white/80 px-3 text-xs font-semibold text-ink shadow-clay-soft transition hover:bg-white"
                >
                  {copiedActionId === ENV_HANDOFF_ID ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                  {copiedActionId === ENV_HANDOFF_ID
                    ? safeText(t, 'common.copied', 'Copied')
                    : safeText(t, 'common.copy', 'Copy')}
                </button>
              </div>
              {launchEnvHandoff.required.length > 0 && (
                <div data-testid="product-readiness-env-handoff-required">
                  <p className="mb-2 text-xs font-bold uppercase tracking-[0.14em] text-error-dark">
                    {safeText(t, 'readiness.envHandoffRequired', 'Required before release')}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {launchEnvHandoff.required.map((envKey) => (
                      <span
                        key={envKey}
                        className="rounded-full bg-error/10 px-2.5 py-1 font-mono text-[11px] font-semibold text-error-dark"
                      >
                        {envKey}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {launchEnvHandoff.optional.length > 0 && (
                <div className="mt-3" data-testid="product-readiness-env-handoff-optional">
                  <p className="mb-2 text-xs font-bold uppercase tracking-[0.14em] text-warning-dark">
                    {safeText(t, 'readiness.envHandoffOptional', 'Optional launch hardening')}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {launchEnvHandoff.optional.map((envKey) => (
                      <span
                        key={envKey}
                        className="rounded-full bg-warning/10 px-2.5 py-1 font-mono text-[11px] font-semibold text-warning-dark"
                      >
                        {envKey}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
          <div className="grid gap-3 lg:grid-cols-2">
            {launchActions.map((action) => (
              <div
                key={action.id}
                data-testid={`product-readiness-next-action-${action.id}`}
                className="rounded-[0.8rem] border border-white/60 bg-white/70 p-4"
              >
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <Badge variant={action.required ? 'error' : 'warning'}>
                    {action.required
                      ? safeText(t, 'readiness.required', 'Required')
                      : safeText(t, 'readiness.optional', 'Optional')}
                  </Badge>
                  <span className="text-sm font-semibold text-ink">
                    {safeText(t, `readiness.check.${action.id}`, action.label)}
                  </span>
                </div>
                <p className="text-sm leading-6 text-ink-muted">
                  {action.remediation}
                </p>
                {action.requiredEnv.length > 0 && (
                  <p className="mt-2 break-words font-mono text-xs font-semibold text-ink-soft">
                    {action.requiredEnv.join(', ')}
                  </p>
                )}
                <button
                  type="button"
                  onClick={() => copyLaunchAction(action)}
                  data-testid={`product-readiness-next-action-copy-${action.id}`}
                  aria-label={`Copy ${action.label} launch action`}
                  className="mt-3 inline-flex h-9 items-center gap-2 rounded-full border border-white/70 bg-white/80 px-3 text-xs font-semibold text-ink shadow-clay-soft transition hover:bg-white"
                >
                  {copiedActionId === action.id ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                  {copiedActionId === action.id
                    ? safeText(t, 'common.copied', 'Copied')
                    : safeText(t, 'common.copy', 'Copy')}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {visibleChecks.map((check) => {
          const meta = getStatusMeta(check.status);
          const Icon = meta.icon;
          const fallbackLabel = CHECK_FALLBACKS[check.id] || check.id;
          const statusText = safeText(t, `readiness.checkStatus.${check.status}`, check.status);
          const detailKey = `readiness.detail.${check.id}.${check.status}`;

          return (
            <div
              key={check.id}
              data-testid={`product-readiness-check-${check.id}`}
              className={`rounded-[1.4rem] border p-4 ${meta.rowClass}`}
            >
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
    </div>
  );
}
