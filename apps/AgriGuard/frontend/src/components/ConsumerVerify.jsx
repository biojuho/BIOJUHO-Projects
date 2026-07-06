import { useCallback, useEffect, useLayoutEffect, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle,
  ChevronDown,
  Clock,
  HelpCircle,
  LockKeyhole,
  MapPin,
  PackageCheck,
  RefreshCcw,
  ScanLine,
  ShieldCheck,
  Thermometer,
} from 'lucide-react';
import { qrVerifyApi } from '../services/api';
import { createQrSessionId } from '../services/qrAnalytics';
import { useToast } from '../contexts/ToastContext';
import { cn } from '../lib/utils';
import { Button } from './ui/Button';

const TRUST_STYLE = {
  Safe: {
    icon: CheckCircle,
    shell: 'border-emerald-300/60 bg-emerald-50 text-emerald-950',
    badge: 'bg-emerald-600 text-white',
    accent: 'text-emerald-700',
  },
  Warning: {
    icon: AlertTriangle,
    shell: 'border-amber-300/70 bg-amber-50 text-amber-950',
    badge: 'bg-amber-500 text-amber-950',
    accent: 'text-amber-700',
  },
  Unknown: {
    icon: HelpCircle,
    shell: 'border-slate-300 bg-slate-50 text-slate-950',
    badge: 'bg-slate-700 text-white',
    accent: 'text-slate-600',
  },
};

const DEFAULT_TRUST_BADGE = {
  status: 'Unknown',
  label: 'Evidence pending',
  reason: 'Public verification evidence is not available yet.',
};

const DEFAULT_TEMPERATURE_SUMMARY = {
  status: 'unknown',
  message: 'Temperature evidence unavailable',
  min_celsius: null,
  max_celsius: null,
  readings_count: 0,
  last_reading_at: null,
};

const DEFAULT_BLOCKCHAIN_PROOF = {
  status: 'pending',
  message: 'Blockchain proof is not available yet.',
  evidence_hash: '',
  records: [],
};
const PUBLIC_VERIFY_LOCALE = 'en-US';

function formatDateTime(value) {
  if (!value) {
    return 'Not available';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return 'Not available';
  }
  return new Intl.DateTimeFormat(PUBLIC_VERIFY_LOCALE, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    timeZoneName: 'short',
  }).format(date);
}

function formatDate(value) {
  if (!value) {
    return 'Pending';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return 'Pending';
  }
  return new Intl.DateTimeFormat(PUBLIC_VERIFY_LOCALE, { dateStyle: 'medium' }).format(date);
}

function formatTrustBadgeLabel(verification, trust) {
  if (trust?.status !== 'Unknown') {
    return trust?.status || 'Unknown';
  }

  return verification?.is_valid ? 'Evidence pending' : 'Not verified';
}

function formatLastEvidenceLabel(verification, trust) {
  return verification?.is_valid && trust?.status && trust.status !== 'Unknown'
    ? 'Last verified'
    : 'Last checked';
}

function MetaNoIndex() {
  useEffect(() => {
    const previousTitle = document.title;
    const existingMeta = document.querySelector('meta[name="robots"]');
    const previousContent = existingMeta?.getAttribute('content') || '';
    const meta = existingMeta || document.createElement('meta');

    document.title = 'AgriGuard Verification';
    meta.setAttribute('name', 'robots');
    meta.setAttribute('content', 'noindex,nofollow');
    if (!existingMeta) {
      document.head.appendChild(meta);
    }

    return () => {
      document.title = previousTitle;
      if (existingMeta) {
        existingMeta.setAttribute('content', previousContent);
      } else {
        meta.remove();
      }
    };
  }, []);

  return null;
}

function EvidenceRow({ icon: Icon, label, value, tone = 'text-slate-800' }) {
  return (
    <div className="flex items-start gap-3 rounded-md border border-slate-200 bg-white px-3 py-3">
      <Icon className={cn('mt-0.5 h-4 w-4 shrink-0', tone)} aria-hidden="true" />
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
        <p className="mt-1 text-sm font-semibold text-slate-950">{value}</p>
      </div>
    </div>
  );
}

function EvidenceSection({ title, children, defaultOpen = false }) {
  return (
    <details className="rounded-lg border border-slate-200 bg-white shadow-sm" open={defaultOpen}>
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-left text-sm font-semibold text-slate-950">
        {title}
        <ChevronDown className="h-4 w-4 text-slate-500" aria-hidden="true" />
      </summary>
      <div className="border-t border-slate-200 px-4 py-4">
        {children}
      </div>
    </details>
  );
}

function LoadingState() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-5">
      <div className="w-full max-w-sm rounded-lg border border-slate-200 bg-white p-6 text-center shadow-sm">
        <ScanLine className="mx-auto h-9 w-9 animate-pulse text-emerald-600" aria-hidden="true" />
        <p className="mt-4 text-base font-semibold text-slate-950">Verifying QR</p>
        <p className="mt-2 text-sm text-slate-600">Checking public traceability evidence.</p>
      </div>
    </div>
  );
}

function ErrorState({ onRetry }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-5">
      <div className="w-full max-w-sm rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <AlertTriangle className="h-9 w-9 text-amber-600" aria-hidden="true" />
        <h1 className="mt-4 text-xl font-bold text-slate-950">Verification unavailable</h1>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          The public verification service did not respond. Try again in a moment or scan again.
        </p>
        <div className="mt-5 flex gap-2">
          <Button type="button" onClick={onRetry} className="bg-slate-950 text-white hover:bg-slate-800">
            <RefreshCcw className="h-4 w-4" />
            Retry
          </Button>
          <Button variant="outline" asChild>
            <Link to="/scan">
              <ArrowLeft className="h-4 w-4" />
              Scan
            </Link>
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function ConsumerVerify() {
  const { qrToken } = useParams();
  const [searchParams] = useSearchParams();
  const [sessionId] = useState(() => searchParams.get('scan_session') || createQrSessionId());
  const [verification, setVerification] = useState(null);
  const [state, setState] = useState({ loading: true, error: false });
  const [reloadAttempt, setReloadAttempt] = useState(0);
  const scanSource = searchParams.get('scan_source') || 'consumer_verify_page';
  const scanVariant = searchParams.get('scan_variant') || 'qr_consumer_v1';
  const { hideToast } = useToast();

  useLayoutEffect(() => {
    hideToast();
  }, [hideToast]);

  const handleRetry = useCallback(() => {
    setVerification(null);
    setState({ loading: true, error: false });
    setReloadAttempt((current) => current + 1);
  }, []);

  useEffect(() => {
    let isCancelled = false;

    const run = async () => {
      try {
        const response = await qrVerifyApi.verify(qrToken, {
          sessionId,
          variantId: scanVariant,
          source: scanSource,
        });
        if (isCancelled) {
          return;
        }
        setVerification(response.data);
        setState({ loading: false, error: false });
      } catch (error) {
        if (isCancelled) {
          return;
        }
        console.error('Failed to verify QR token', error);
        setState({ loading: false, error: true });
      }
    };

    void run();

    return () => {
      isCancelled = true;
    };
  }, [qrToken, reloadAttempt, scanSource, scanVariant, sessionId]);

  const trust = verification?.trust_badge || DEFAULT_TRUST_BADGE;
  const trustStyle = useMemo(() => TRUST_STYLE[trust?.status] || TRUST_STYLE.Unknown, [trust?.status]);
  const trustBadgeLabel = formatTrustBadgeLabel(verification, trust);
  const lastEvidenceLabel = formatLastEvidenceLabel(verification, trust);
  const TrustIcon = trustStyle.icon;

  if (state.loading) {
    return (
      <>
        <MetaNoIndex />
        <LoadingState />
      </>
    );
  }

  if (state.error || !verification) {
    return (
      <>
        <MetaNoIndex />
        <ErrorState onRetry={handleRetry} />
      </>
    );
  }

  const temperature = verification.temperature_summary || DEFAULT_TEMPERATURE_SUMMARY;
  const proof = verification.blockchain_proof || DEFAULT_BLOCKCHAIN_PROOF;
  const route = Array.isArray(verification.route) ? verification.route : [];
  const product = verification.product;
  const batch = verification.batch;
  const proofRecords = Array.isArray(proof.records) ? proof.records : [];
  const hasProofRecords = proofRecords.length > 0;

  return (
    <div className="min-h-screen bg-slate-100 text-slate-950">
      <MetaNoIndex />
      <main className="mx-auto flex w-full max-w-2xl flex-col gap-4 px-4 py-4 sm:py-8" aria-live="polite">
        <div className="flex items-center justify-between gap-3">
          <Link to="/scan" className="inline-flex items-center gap-2 text-sm font-semibold text-slate-700">
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            Scan
          </Link>
          <span className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-semibold text-slate-600">
            <LockKeyhole className="h-3.5 w-3.5" aria-hidden="true" />
            Public view
          </span>
        </div>

        <section className={cn('rounded-lg border p-5 shadow-sm', trustStyle.shell)}>
          <div className="flex items-start gap-4">
            <div className="rounded-lg bg-white/80 p-2 shadow-sm">
              <TrustIcon className={cn('h-8 w-8', trustStyle.accent)} aria-hidden="true" />
            </div>
            <div className="min-w-0 flex-1">
              <span data-testid="consumer-trust-badge" className={cn('inline-flex rounded-md px-2 py-1 text-xs font-bold', trustStyle.badge)}>
                {trustBadgeLabel}
              </span>
              <h1 data-testid="consumer-trust-heading" className="mt-3 text-xl font-bold leading-tight sm:text-2xl">{trust.label}</h1>
              <p className="mt-2 text-sm leading-6">{trust.reason}</p>
            </div>
          </div>
          <div className="mt-5 rounded-md bg-white/75 px-3 py-3 text-sm">
            <p className="font-semibold">{product?.name || 'Unverified AgriGuard QR'}</p>
            <p className="mt-1 text-slate-600">{verification.consumer_notice}</p>
          </div>
        </section>

        <section className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <EvidenceRow icon={MapPin} label="Origin" value={product?.origin || 'Not verified'} tone="text-emerald-700" />
          <EvidenceRow icon={PackageCheck} label="Batch" value={batch?.batch_code || 'Hidden'} tone="text-blue-700" />
          <EvidenceRow icon={Thermometer} label="Temperature" value={temperature.message} tone="text-cyan-700" />
          <EvidenceRow icon={Clock} label={lastEvidenceLabel} value={formatDateTime(verification.last_verified_at)} tone="text-slate-700" />
        </section>

        {batch && (
          <EvidenceSection title="Batch and origin" defaultOpen>
            <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
              <div>
                <dt className="font-medium text-slate-500">Category</dt>
                <dd className="mt-1 font-semibold text-slate-950">{product?.category || 'Not available'}</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-500">Harvest date</dt>
                <dd className="mt-1 font-semibold text-slate-950">{formatDate(batch.harvest_date)}</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-500">Cold-chain required</dt>
                <dd className="mt-1 font-semibold text-slate-950">{batch.cold_chain_required ? 'Yes' : 'No'}</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-500">Recall status</dt>
                <dd className="mt-1 font-semibold text-slate-950">{(batch.recall_status || 'not_reported').replace(/_/g, ' ')}</dd>
              </div>
            </dl>
          </EvidenceSection>
        )}

        <EvidenceSection title="Route evidence" defaultOpen={route.length > 0}>
          {route.length > 0 ? (
            <ol className="space-y-3">
              {route.map((checkpoint) => (
                <li key={`${checkpoint.timestamp}-${checkpoint.status}-${checkpoint.location}`} className="rounded-md border border-slate-200 bg-slate-50 p-3">
                  <p className="text-sm font-semibold text-slate-950">{checkpoint.status}</p>
                  <p className="mt-1 text-sm text-slate-600">{checkpoint.location}</p>
                  <p className="mt-2 text-xs text-slate-500">{formatDateTime(checkpoint.timestamp)}</p>
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-sm leading-6 text-slate-600">No public route checkpoints are available for this code.</p>
          )}
        </EvidenceSection>

        <EvidenceSection title="Temperature summary" defaultOpen>
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <dt className="font-medium text-slate-500">Status</dt>
              <dd className="mt-1 font-semibold capitalize text-slate-950">{temperature.status}</dd>
            </div>
            <div>
              <dt className="font-medium text-slate-500">Readings</dt>
              <dd className="mt-1 font-semibold text-slate-950">{temperature.readings_count}</dd>
            </div>
            <div>
              <dt className="font-medium text-slate-500">Min</dt>
              <dd className="mt-1 font-semibold text-slate-950">{temperature.min_celsius ?? '--'}C</dd>
            </div>
            <div>
              <dt className="font-medium text-slate-500">Max</dt>
              <dd className="mt-1 font-semibold text-slate-950">{temperature.max_celsius ?? '--'}C</dd>
            </div>
            <div className="col-span-2">
              <dt className="font-medium text-slate-500">Latest reading</dt>
              <dd className="mt-1 font-semibold text-slate-950">{formatDateTime(temperature.last_reading_at)}</dd>
            </div>
          </dl>
        </EvidenceSection>

        <EvidenceSection title="Blockchain proof">
          <div className="rounded-md bg-slate-50 p-3 text-sm">
            <p className="font-semibold capitalize text-slate-950">{proof.status}</p>
            <p className="mt-1 leading-6 text-slate-600">{proof.message}</p>
            <p className="mt-3 break-all font-mono text-xs text-slate-500">Evidence hash: {proof.evidence_hash || 'Pending'}</p>
          </div>
          {hasProofRecords && (
            <ol className="mt-3 space-y-2">
              {proofRecords.map((record) => (
                <li key={`${record.tx_hash}-${record.block}-${record.event_type}`} className="rounded-md border border-slate-200 p-3 text-sm">
                  <p className="font-semibold text-slate-950">{record.event_type}</p>
                  <p data-testid="consumer-proof-tx" className="mt-1 break-all font-mono text-xs text-slate-600">TX {record.tx_hash}</p>
                  <p className="mt-1 text-xs text-slate-500">Block {record.block} - {formatDateTime(record.timestamp)}</p>
                </li>
              ))}
            </ol>
          )}
        </EvidenceSection>

        <p className="px-1 pb-2 text-center text-xs leading-5 text-slate-500">
          Session {sessionId.slice(-8)} - Verified {formatDateTime(verification.verified_at)}
        </p>
      </main>
    </div>
  );
}
