import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Clipboard,
  KeyRound,
  Loader2,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react';
import { qrTokenAdminApi, getOperatorToken, setOperatorToken } from '../services/api';
import { Card, CardContent, CardHeader, CardTitle } from './ui/Card';
import { Badge } from './ui/Badge';
import { Button } from './ui/Button';
import { Input } from './ui/Input';
import { cn } from '../lib/utils';

const PAGE_SIZE = 20;
const STATUS_OPTIONS = ['all', 'active', 'revoked', 'expired'];

const statusVariant = {
  active: 'success',
  revoked: 'destructive',
  expired: 'warning',
};

function formatDateTime(value) {
  if (!value) return 'Not set';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Invalid date';
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatStatusLabel(value) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function TokenStatusBadge({ status }) {
  return (
    <Badge variant={statusVariant[status] || 'outline'} className="capitalize">
      {status === 'active' && <ShieldCheck className="h-3.5 w-3.5" />}
      {status === 'revoked' && <ShieldAlert className="h-3.5 w-3.5" />}
      {status === 'expired' && <AlertTriangle className="h-3.5 w-3.5" />}
      {status}
    </Badge>
  );
}

function TokenStat({ label, value }) {
  return (
    <div className="rounded-lg border border-border bg-white/[0.03] px-4 py-3">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-foreground">{value}</p>
    </div>
  );
}

export default function QRTokenManager() {
  const labelResultRef = useRef(null);
  const [productId, setProductId] = useState('');
  const [loadedProductId, setLoadedProductId] = useState('');
  const [tokenStatus, setTokenStatus] = useState('all');
  const [page, setPage] = useState(1);
  const [tokenState, setTokenState] = useState({
    loading: false,
    error: null,
    data: null,
  });
  const [operatorTokenInput, setOperatorTokenInput] = useState(() => getOperatorToken());
  const [hasSavedOperatorToken, setHasSavedOperatorToken] = useState(() => Boolean(getOperatorToken()));
  const [pendingAction, setPendingAction] = useState(null);
  const [actionState, setActionState] = useState({
    loading: false,
    error: null,
    success: null,
  });
  const [copied, setCopied] = useState(false);

  const loadTokens = useCallback(async ({ nextProductId = loadedProductId, nextStatus = tokenStatus, nextPage = page } = {}) => {
    const normalizedProductId = nextProductId.trim();
    if (!normalizedProductId) {
      setTokenState({ loading: false, error: 'Enter a product ID to load QR tokens.', data: null });
      return;
    }

    setTokenState((current) => ({ ...current, loading: true, error: null }));
    setActionState((current) => ({ ...current, error: null }));

    try {
      const response = await qrTokenAdminApi.listByProduct(normalizedProductId, {
        tokenStatus: nextStatus,
        page: nextPage,
        pageSize: PAGE_SIZE,
      });
      setLoadedProductId(normalizedProductId);
      setProductId(normalizedProductId);
      setTokenStatus(nextStatus);
      setPage(response.data.page || nextPage);
      setTokenState({ loading: false, error: null, data: response.data });
    } catch (error) {
      setTokenState({
        loading: false,
        error: error.response?.data?.detail || error.message || 'Failed to load QR tokens.',
        data: null,
      });
    }
  }, [loadedProductId, page, tokenStatus]);

  useEffect(() => {
    if (!loadedProductId) return;
    // Re-fetch when the operator changes status/page controls after an initial search.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadTokens({ nextProductId: loadedProductId, nextStatus: tokenStatus, nextPage: page });
  }, [loadedProductId, loadTokens, page, tokenStatus]);

  useEffect(() => {
    if (!actionState.success?.qrCode) return;
    labelResultRef.current?.scrollIntoView({ block: 'start', behavior: 'auto' });
  }, [actionState.success?.qrCode]);

  const handleSearch = useCallback((event) => {
    event.preventDefault();
    setPendingAction(null);
    setActionState({ loading: false, error: null, success: null });
    setPage(1);
    loadTokens({ nextProductId: productId, nextStatus: tokenStatus, nextPage: 1 });
  }, [loadTokens, productId, tokenStatus]);

  const saveOperatorToken = useCallback(() => {
    setOperatorToken(operatorTokenInput);
    setHasSavedOperatorToken(Boolean(operatorTokenInput.trim()));
    setActionState({
      loading: false,
      error: null,
      success: operatorTokenInput.trim() ? { message: 'Operator token saved for this browser.' } : { message: 'Operator token cleared.' },
    });
  }, [operatorTokenInput]);

  const confirmAction = useCallback(async () => {
    if (!pendingAction) return;
    setActionState({ loading: true, error: null, success: null });
    setCopied(false);

    try {
      if (pendingAction.type === 'reissue') {
        const response = await qrTokenAdminApi.reissue(loadedProductId, { revokeExisting: true });
        setActionState({
          loading: false,
          error: null,
          success: {
            message: 'QR token reissued. Print or copy the new label URL now.',
            qrCode: response.data.qr_code,
            token: response.data.token,
          },
        });
      } else {
        await qrTokenAdminApi.revoke(pendingAction.token.id);
        setActionState({
          loading: false,
          error: null,
          success: { message: `Token ${pendingAction.token.token_prefix} revoked.` },
        });
      }
      setPendingAction(null);
      await loadTokens({ nextProductId: loadedProductId, nextStatus: tokenStatus, nextPage: page });
    } catch (error) {
      setActionState({
        loading: false,
        error: error.response?.data?.detail || error.message || 'QR token action failed.',
        success: null,
      });
    }
  }, [loadTokens, loadedProductId, page, pendingAction, tokenStatus]);

  const copyQrCode = useCallback(async () => {
    if (!actionState.success?.qrCode || !navigator.clipboard) return;
    await navigator.clipboard.writeText(actionState.success.qrCode);
    setCopied(true);
  }, [actionState.success]);

  const tokens = tokenState.data?.items || [];
  const hasLoaded = Boolean(tokenState.data);
  const currentPage = tokenState.data?.page || page;
  const totalPages = tokenState.data?.total_pages || 1;
  const statusSummary = useMemo(() => [
    ['Active', tokenState.data?.active_count ?? 0],
    ['Revoked', tokenState.data?.revoked_count ?? 0],
    ['Expired', tokenState.data?.expired_count ?? 0],
  ], [tokenState.data]);

  return (
    <div className="mx-auto max-w-7xl space-y-5 px-4 py-5 text-foreground sm:space-y-8 sm:p-8">
      <div className="flex flex-col gap-3 sm:gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="mb-3 inline-flex items-center gap-2 rounded-md border border-emerald-500/20 bg-emerald-500/10 px-3 py-1 text-sm text-emerald-300">
            <KeyRound className="h-4 w-4" />
            Operator QR Controls
          </div>
          <h1 data-testid="qr-token-heading" className="max-w-full text-2xl font-bold leading-tight text-foreground sm:text-3xl">QR Token Management</h1>
          <p className="mt-2 max-w-3xl text-sm leading-snug text-muted-foreground">
            Review label token state, revoke compromised QR codes, and reissue a new label token without exposing stored token hashes.
          </p>
        </div>

        <Card data-testid="qr-token-operator-token-card" className="w-full border-primary/20 bg-primary/5 lg:w-[28rem]">
          <CardContent className="p-3 sm:p-4">
            <label htmlFor="operator-token" className="text-sm font-medium text-foreground">
              Operator bearer token
            </label>
            <div className="mt-2 grid grid-cols-[minmax(0,1fr)_5rem] gap-2">
              <Input
                id="operator-token"
                type="password"
                value={operatorTokenInput}
                onChange={(event) => setOperatorTokenInput(event.target.value)}
                placeholder="Paste Firebase/operator token"
                className="min-h-10 sm:min-h-11"
              />
              <Button type="button" onClick={saveOperatorToken} className="min-h-10 px-3 sm:min-h-11">
                Save
              </Button>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              {hasSavedOperatorToken ? 'A token is saved locally for operator API calls.' : 'No token saved. Protected actions will return 401.'}
            </p>
          </CardContent>
        </Card>
      </div>

      <Card data-testid="qr-token-filter-panel">
        <CardContent className="p-4 sm:p-6">
          <form onSubmit={handleSearch} className="grid grid-cols-2 gap-3 lg:grid-cols-[minmax(0,1fr)_12rem_auto] lg:items-end">
            <div className="col-span-2 min-w-0 lg:col-span-1">
              <label htmlFor="product-id" className="text-sm font-medium text-muted-foreground">
                Product ID
              </label>
              <Input
                id="product-id"
                value={productId}
                onChange={(event) => setProductId(event.target.value)}
                placeholder="e.g. product-reissue-1"
                className="mt-2 min-h-10 font-mono sm:min-h-11"
              />
            </div>
            <div className="min-w-0">
              <label htmlFor="token-status" className="text-sm font-medium text-muted-foreground">
                Token state
              </label>
              <select
                id="token-status"
                value={tokenStatus}
                onChange={(event) => {
                  setTokenStatus(event.target.value);
                  setPage(1);
                }}
                className="mt-2 flex min-h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:min-h-11"
              >
                {STATUS_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {formatStatusLabel(option)}
                  </option>
                ))}
              </select>
            </div>
            <Button type="submit" className="min-h-10 sm:min-h-11" disabled={tokenState.loading}>
              {tokenState.loading ? <Loader2 className="animate-spin" /> : <Search />}
              Load tokens
            </Button>
          </form>
        </CardContent>
      </Card>

      <div aria-live="polite" role="status" className="min-h-0 text-sm empty:hidden">
        {tokenState.loading && <span className="text-muted-foreground">Loading QR token state...</span>}
        {tokenState.error && (
          <span className="inline-flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-4 w-4" />
            {tokenState.error}
          </span>
        )}
        {actionState.error && (
          <span className="inline-flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-4 w-4" />
            {actionState.error}
          </span>
        )}
        {actionState.success?.message && (
          <span className="inline-flex items-center gap-2 text-emerald-300">
            <CheckCircle2 className="h-4 w-4" />
            {actionState.success.message}
          </span>
        )}
      </div>

      {actionState.success?.qrCode && (
        <Card ref={labelResultRef} data-testid="qr-token-reissue-result" className="scroll-mt-24 border-emerald-500/30 bg-emerald-500/10">
          <CardContent className="p-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-emerald-100">New label URL ready</h2>
                <p className="mt-1 break-all font-mono text-sm text-emerald-50">{actionState.success.qrCode}</p>
                <p className="mt-2 text-xs text-emerald-200/80">
                  Raw token is shown once in this response for label production.
                </p>
              </div>
              <Button type="button" variant="outline" onClick={copyQrCode} className="min-h-11">
                <Clipboard />
                {copied ? 'Copied' : 'Copy URL'}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {pendingAction && (
        <Card className="border-amber-500/30 bg-amber-500/10">
          <CardContent className="p-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-amber-100">
                  Confirm {pendingAction.type === 'reissue' ? 'QR token reissue' : 'token revocation'}
                </h2>
                <p className="mt-1 text-sm text-amber-100/80">
                  {pendingAction.type === 'reissue'
                    ? `A new label token will be created for ${loadedProductId}, and active existing tokens will be revoked.`
                    : `Token ${pendingAction.token.token_prefix} will stop passing public verification immediately.`}
                </p>
              </div>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Button type="button" variant="outline" onClick={() => setPendingAction(null)} disabled={actionState.loading} className="min-h-11">
                  Cancel
                </Button>
                <Button type="button" variant={pendingAction.type === 'revoke' ? 'destructive' : 'default'} onClick={confirmAction} disabled={actionState.loading} className="min-h-11">
                  {actionState.loading ? <Loader2 className="animate-spin" /> : <RefreshCw />}
                  Confirm
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {hasLoaded && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {statusSummary.map(([label, value]) => (
            <TokenStat key={label} label={label} value={value} />
          ))}
        </div>
      )}

      <Card>
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <CardTitle className="text-lg">Product QR tokens</CardTitle>
          {hasLoaded && (
            <Button type="button" variant="secondary" onClick={() => setPendingAction({ type: 'reissue' })} disabled={!loadedProductId || actionState.loading} className="min-h-11">
              <RefreshCw />
              Reissue label
            </Button>
          )}
        </CardHeader>
        <CardContent>
          {!hasLoaded && !tokenState.loading && (
            <div className="rounded-lg border border-dashed border-border p-10 text-center">
              <KeyRound className="mx-auto h-10 w-10 text-muted-foreground" />
              <h2 className="mt-4 text-lg font-semibold">Load a product to manage QR tokens</h2>
              <p className="mt-2 text-sm text-muted-foreground">
                Token hashes stay server-side. Operators only see prefixes, state, scan counts, and timestamps.
              </p>
            </div>
          )}

          {hasLoaded && tokens.length === 0 && (
            <div className="rounded-lg border border-dashed border-border p-10 text-center">
              <AlertTriangle className="mx-auto h-10 w-10 text-amber-300" />
              <h2 className="mt-4 text-lg font-semibold">No tokens match this filter</h2>
              <p className="mt-2 text-sm text-muted-foreground">Try another state filter or reissue a label token.</p>
            </div>
          )}

          {tokens.length > 0 && (
            <div className="overflow-visible md:overflow-x-auto">
              <table
                data-testid="qr-token-table"
                className="w-full border-separate border-spacing-0 text-left text-sm md:min-w-[760px] md:border-collapse"
              >
                <thead className="hidden border-b border-border text-xs uppercase tracking-wide text-muted-foreground md:table-header-group">
                  <tr>
                    <th scope="col" className="py-3 pr-4">Token</th>
                    <th scope="col" className="py-3 pr-4">State</th>
                    <th scope="col" className="py-3 pr-4">Batch</th>
                    <th scope="col" className="py-3 pr-4">Scans</th>
                    <th scope="col" className="py-3 pr-4">Last verified</th>
                    <th scope="col" className="py-3 pr-4">Expires</th>
                    <th scope="col" className="py-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="block space-y-3 md:table-row-group md:divide-y md:divide-border md:space-y-0">
                  {tokens.map((token) => (
                    <tr
                      key={token.id}
                      data-testid="qr-token-row"
                      className="block rounded-lg border border-border bg-background/40 p-4 align-top md:table-row md:border-0 md:bg-transparent md:p-0"
                    >
                      <td className="block border-b border-border/60 pb-3 md:table-cell md:border-0 md:py-4 md:pr-4">
                        <span className="mb-2 block text-xs font-semibold uppercase tracking-wide text-muted-foreground md:hidden">
                          Token
                        </span>
                        <div className="break-all font-mono text-foreground">{token.token_prefix}</div>
                        <div className="mt-1 max-w-full break-all text-xs text-muted-foreground md:max-w-52 md:truncate">{token.id}</div>
                      </td>
                      <td className="flex items-center justify-between gap-3 border-b border-border/60 py-3 md:table-cell md:border-0 md:py-4 md:pr-4">
                        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground md:hidden">
                          State
                        </span>
                        <TokenStatusBadge status={token.status} />
                      </td>
                      <td className="flex items-center justify-between gap-3 border-b border-border/60 py-3 md:table-cell md:border-0 md:py-4 md:pr-4">
                        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground md:hidden">
                          Batch
                        </span>
                        <span className="break-all text-right font-mono text-xs text-muted-foreground md:text-left">{token.batch_code}</span>
                      </td>
                      <td className="flex items-center justify-between gap-3 border-b border-border/60 py-3 md:table-cell md:border-0 md:py-4 md:pr-4">
                        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground md:hidden">
                          Scans
                        </span>
                        <span>{token.scan_count}</span>
                      </td>
                      <td className="flex items-center justify-between gap-3 border-b border-border/60 py-3 text-muted-foreground md:table-cell md:border-0 md:py-4 md:pr-4">
                        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground md:hidden">
                          Last verified
                        </span>
                        <span className="text-right md:text-left">{formatDateTime(token.last_verified_at)}</span>
                      </td>
                      <td className="flex items-center justify-between gap-3 border-b border-border/60 py-3 text-muted-foreground md:table-cell md:border-0 md:py-4 md:pr-4">
                        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground md:hidden">
                          Expires
                        </span>
                        <span className="text-right md:text-left">{formatDateTime(token.expires_at)}</span>
                      </td>
                      <td className="block pt-4 md:table-cell md:py-4 md:text-right">
                        <span className="mb-2 block text-xs font-semibold uppercase tracking-wide text-muted-foreground md:hidden">
                          Action
                        </span>
                        <Button
                          type="button"
                          variant="destructive"
                          size="sm"
                          onClick={() => setPendingAction({ type: 'revoke', token })}
                          disabled={token.status !== 'active' || actionState.loading}
                          className={cn('min-h-10 w-full justify-center md:w-auto', token.status !== 'active' && 'opacity-40')}
                        >
                          Revoke
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {hasLoaded && (
            <div className="mt-5 flex flex-col gap-3 border-t border-border pt-4 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
              <span aria-live="polite">
                Showing {tokens.length} of {tokenState.data.total} matching tokens for {loadedProductId}
              </span>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((value) => Math.max(1, value - 1))}
                  disabled={currentPage === 1}
                >
                  Previous
                </Button>
                <span className="min-w-20 text-center">Page {currentPage} / {totalPages}</span>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
                  disabled={currentPage === totalPages}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
