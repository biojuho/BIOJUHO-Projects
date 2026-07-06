import { useState, useCallback, useEffect } from 'react';
import { Activity, Package, ShieldCheck, Thermometer, AlertTriangle, CheckCircle2, TrendingUp, MapPin, Clock3, X } from 'lucide-react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, PieChart, Pie, Cell, Legend } from 'recharts';
import api, { getOperatorToken, setOperatorToken, withOperatorAuth } from '../../services/api';
import { useToast } from '../../contexts/ToastContext';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';

const QR_KPI_TIMEZONE_STORAGE_KEY = 'agriguard.qrKpi.reportingTimezone';
const DEFAULT_REPORTING_TIMEZONES = ['UTC', 'Asia/Seoul', 'America/Los_Angeles', 'Europe/Amsterdam'];
const DASHBOARD_LOCALE = 'en-US';
const DASHBOARD_NUMBER_FORMATTER = new Intl.NumberFormat(DASHBOARD_LOCALE);

function getDashboardLoadError(error) {
  const detail = error?.message || 'Dashboard summary could not be loaded.';

  if (error?.response?.status === 401) {
    return {
      kind: 'auth',
      title: 'Operator authentication required',
      description: 'Paste a Firebase/operator token below, or save one in QR Tokens or Sensors.',
      toast: 'Operator authentication required for dashboard metrics.',
      detail,
    };
  }

  return {
    kind: 'backend',
    title: 'Backend connection failed',
    description: 'Confirm the AgriGuard backend on port 8002 is running.',
    toast: 'Backend connection failed: check the port 8002 server.',
    detail,
  };
}

function getBrowserTimezone() {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
}

function getInitialReportingTimezone() {
  try {
    return window.localStorage.getItem(QR_KPI_TIMEZONE_STORAGE_KEY) || getBrowserTimezone();
  } catch {
    return getBrowserTimezone();
  }
}

function getReportingTimezoneOptions(selectedTimezone) {
  return Array.from(new Set([getBrowserTimezone(), ...DEFAULT_REPORTING_TIMEZONES, selectedTimezone].filter(Boolean)));
}

export function formatDashboardStatusLabel(value) {
  const raw = String(value || '').trim();
  const compact = raw.replace(/[^a-z0-9]/gi, '').toLowerCase();
  const aliases = {
    delivered: 'Delivered',
    deliveredtowarehouse: 'Warehouse',
    harvested: 'Harvested',
    intransit: 'In Transit',
    planted: 'Planted',
    qualitycheckpassed: 'QC',
    shipped: 'Shipped',
  };
  if (aliases[compact]) return aliases[compact];

  return raw
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\s+/g, ' ')
    .trim();
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [qrKpis, setQrKpis] = useState(null);
  const [qrKpiTrend, setQrKpiTrend] = useState(null);
  const [qrKpiTimezone, setQrKpiTimezone] = useState(getInitialReportingTimezone);
  const [qrKpiError, setQrKpiError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [operatorTokenInput, setOperatorTokenInput] = useState(() => getOperatorToken());
  const { showToast } = useToast();

  const fetchDashboardSummary = useCallback(() => {
    api.get('/dashboard/summary', withOperatorAuth())
      .then(res => {
        setData(res.data);
        setLoading(false);
      })
      .catch(err => {
        const dashboardError = getDashboardLoadError(err);
        setError(dashboardError);
        setLoading(false);
        showToast(dashboardError.toast, 'error');
      });
  }, [showToast]);

  useEffect(() => {
    fetchDashboardSummary();
  }, [fetchDashboardSummary]);

  const handleSaveOperatorToken = useCallback((event) => {
    event.preventDefault();
    setOperatorToken(operatorTokenInput);
    setLoading(true);
    setError(null);
    showToast(
      operatorTokenInput.trim()
        ? 'Operator token saved. Retrying dashboard metrics.'
        : 'Operator token cleared. Protected dashboard metrics will still require authentication.',
      'success',
    );
    fetchDashboardSummary();
  }, [fetchDashboardSummary, operatorTokenInput, showToast]);

  const handleClearOperatorToken = useCallback(() => {
    setOperatorToken('');
    setOperatorTokenInput('');
    showToast('Operator token cleared. Protected dashboard metrics will still require authentication.', 'success');
  }, [showToast]);

  useEffect(() => {
    try {
      window.localStorage.setItem(QR_KPI_TIMEZONE_STORAGE_KEY, qrKpiTimezone);
    } catch {
      // Storage is optional; the selected timezone still applies for the active session.
    }
  }, [qrKpiTimezone]);

  useEffect(() => {
    let isCancelled = false;

    Promise.allSettled([
      api.get('/qr-events/kpis'),
      api.get('/qr-events/kpis/trend', { params: { days: 7, timezone: qrKpiTimezone } }),
    ])
      .then(([kpiResult, trendResult]) => {
        if (isCancelled) return;

        if (kpiResult.status === 'fulfilled') {
          setQrKpis(kpiResult.value.data);
          setQrKpiError(null);
        } else {
          setQrKpis(null);
          setQrKpiError(kpiResult.reason?.message || 'QR KPI data unavailable');
        }

        if (trendResult.status === 'fulfilled') {
          setQrKpiTrend(trendResult.value.data);
        } else {
          setQrKpiTrend(null);
        }
      })
      .catch((err) => {
        if (isCancelled) return;
        setQrKpis(null);
        setQrKpiTrend(null);
        setQrKpiError(err.message || 'QR KPI data unavailable');
      });

    return () => {
      isCancelled = true;
    };
  }, [qrKpiTimezone]);

  if (loading) return <DashboardSkeleton />;

  if (error) {
    return (
      <Card className="m-8 border-destructive/30 bg-destructive/5">
        <CardContent className="p-8 text-center">
          <AlertTriangle className="mx-auto h-12 w-12 text-destructive mb-4" />
          <h2 className="text-xl font-semibold text-destructive">{error.title}</h2>
          <p className="text-destructive/70 mt-2 text-sm">{error.description}</p>
          <p
            data-testid="dashboard-error-detail"
            title={error.detail}
            className="mt-1 break-all select-all text-xs font-mono text-muted-foreground"
          >
            {error.detail}
          </p>
          {error.kind === 'auth' && (
            <form onSubmit={handleSaveOperatorToken} className="mx-auto mt-6 max-w-xl text-left">
              <label htmlFor="dashboard-operator-token" className="text-sm font-medium text-foreground">
                Operator bearer token
              </label>
              <div className="mt-2 grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto_auto]">
                <Input
                  id="dashboard-operator-token"
                  type="password"
                  value={operatorTokenInput}
                  onChange={(event) => setOperatorTokenInput(event.target.value)}
                  placeholder="Paste Firebase/operator token"
                  autoComplete="off"
                  spellCheck={false}
                  className="min-h-11"
                />
                <Button type="submit" className="min-h-11">
                  Save and retry
                </Button>
                {operatorTokenInput && (
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={handleClearOperatorToken}
                    className="min-h-11 justify-start px-3 text-muted-foreground hover:text-foreground"
                  >
                    <X className="h-4 w-4" />
                    Clear token
                  </Button>
                )}
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                The token stays in this browser local storage and is used only for operator API calls.
              </p>
            </form>
          )}
        </CardContent>
      </Card>
    );
  }

  const statusDist = data?.status_distribution || {};
  const originDist = data?.origin_distribution || {};
  const statusEntries = Object.entries(statusDist).sort((a, b) => b[1] - a[1]);
  const originEntries = Object.entries(originDist).sort((a, b) => b[1] - a[1]);
  const statusChartData = statusEntries.map(([name, value]) => ({
    name,
    label: formatDashboardStatusLabel(name),
    value,
  }));
  const originChartData = originEntries.map(([name, value]) => ({ name, value }));

  const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899', '#f43f5e'];

  return (
    <div data-testid="dashboard-page" className="mx-auto max-w-7xl space-y-5 px-4 py-5 animate-in fade-in duration-500 sm:space-y-8 sm:p-8">
      {/* Header */}
      <div data-testid="dashboard-hero-header" className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="max-w-full text-2xl font-bold leading-tight bg-gradient-to-r from-primary to-emerald-600 bg-clip-text text-transparent sm:text-3xl">
          AgriGuard Supply Chain Status
        </h1>
        <Badge variant="success" className="gap-1.5 whitespace-nowrap">
          <CheckCircle2 className="h-3.5 w-3.5" />
          Live data
        </Badge>
      </div>

      <ConsumerQrKpiStrip
        qrKpis={qrKpis}
        trend={qrKpiTrend}
        error={qrKpiError}
        selectedTimezone={qrKpiTimezone}
        timezoneOptions={getReportingTimezoneOptions(qrKpiTimezone)}
        onTimezoneChange={setQrKpiTimezone}
      />

      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4 lg:gap-6">
        <StatCard
          title="Total products"
          value={data?.total_products ?? 0}
          icon={<Package className="h-5 w-5" />}
          color="text-blue-400"
          bg="bg-blue-500/15"
        />
        <StatCard
          title="Certified products"
          value={data?.certified_products ?? 0}
          icon={<ShieldCheck className="h-5 w-5" />}
          color="text-primary"
          bg="bg-primary/15"
          sub={data?.total_products > 0
            ? `${Math.round((data.certified_products / data.total_products) * 100)}% certified`
            : '—'}
        />
        <StatCard
          title="Cold-chain products"
          value={data?.cold_chain_products ?? 0}
          icon={<Thermometer className="h-5 w-5" />}
          color="text-cyan-400"
          bg="bg-cyan-500/15"
        />
        <StatCard
          title="Tracking events"
          value={data?.total_tracking_events ?? 0}
          icon={<Activity className="h-5 w-5" />}
          color="text-violet-400"
          bg="bg-violet-500/15"
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Status Distribution */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-primary" />
              Tracking status distribution
            </CardTitle>
          </CardHeader>
          <CardContent>
            {statusEntries.length === 0 ? (
              <div className="flex items-center justify-center h-40 text-muted-foreground text-sm">
                No tracking events yet
              </div>
            ) : (
              <div className="h-64 min-w-0">
                <ResponsiveContainer width="100%" height={256} minWidth={320}>
                  <BarChart
                    data={statusChartData}
                    layout="vertical"
                    margin={{ top: 5, right: 30, left: 40, bottom: 5 }}
                    title="Tracking status distribution chart"
                    desc="Keyboard-navigable vertical bar chart showing product tracking status counts."
                  >
                    <XAxis type="number" hide />
                    <YAxis dataKey="label" type="category" axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 13 }} width={80} />
                    <Tooltip
                      cursor={{fill: 'rgba(255,255,255,0.03)'}}
                      contentStyle={{ borderRadius: '12px', border: '1px solid rgba(255,255,255,0.1)', background: '#1e293b', color: '#e2e8f0' }}
                    />
                    <Bar dataKey="value" fill="#10b981" radius={[0, 6, 6, 0]} barSize={24}>
                      {statusChartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={'url(#colorGradient)'} />
                      ))}
                    </Bar>
                    <defs>
                      <linearGradient id="colorGradient" x1="0" y1="0" x2="1" y2="0">
                        <stop offset="0%" stopColor="#34d399" />
                        <stop offset="100%" stopColor="#14b8a6" />
                      </linearGradient>
                    </defs>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Origin Distribution */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <MapPin className="h-4 w-4 text-blue-400" />
              Products by origin
            </CardTitle>
          </CardHeader>
          <CardContent>
            {originEntries.length === 0 ? (
              <div className="flex items-center justify-center h-40 text-muted-foreground text-sm">
                No products yet
              </div>
            ) : (
              <div className="h-64 min-w-0">
                <ResponsiveContainer width="100%" height={256} minWidth={320}>
                  <PieChart
                    title="Product origin distribution chart"
                    desc="Keyboard-navigable pie chart showing product counts by origin."
                  >
                    <Pie
                      data={originChartData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={80}
                      paddingAngle={5}
                      dataKey="value"
                    >
                      {originChartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{ borderRadius: '12px', border: '1px solid rgba(255,255,255,0.1)', background: '#1e293b', color: '#e2e8f0' }}
                    />
                    <Legend verticalAlign="bottom" height={36} iconType="circle" />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function formatPercent(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return '0%';
  return `${Math.round(numeric * 1000) / 10}%`;
}

function formatKpiStatus(status) {
  if (status === 'on_track') return 'On track';
  if (status === 'below_target') return 'Below target';
  return 'No data';
}

function formatDashboardCount(value) {
  return DASHBOARD_NUMBER_FORMATTER.format(Number(value ?? 0));
}

function formatTrendDate(date) {
  const parsed = new Date(`${date}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return date;
  return new Intl.DateTimeFormat(DASHBOARD_LOCALE, { month: 'short', day: '2-digit', timeZone: 'UTC' }).format(parsed);
}

function kpiTone(status) {
  if (status === 'on_track') {
    return {
      border: 'border-emerald-500/25',
      bg: 'bg-emerald-500/10',
      text: 'text-emerald-300',
      badge: 'success',
      icon: <ShieldCheck className="h-4 w-4" />,
    };
  }
  if (status === 'below_target') {
    return {
      border: 'border-amber-500/25',
      bg: 'bg-amber-500/10',
      text: 'text-amber-300',
      badge: 'warning',
      icon: <AlertTriangle className="h-4 w-4" />,
    };
  }
  return {
    border: 'border-slate-500/25',
    bg: 'bg-slate-500/10',
    text: 'text-slate-300',
    badge: 'secondary',
    icon: <Activity className="h-4 w-4" />,
  };
}

function ConsumerQrKpiStrip({ qrKpis, trend, error, selectedTimezone, timezoneOptions, onTimezoneChange }) {
  const successTone = kpiTone(qrKpis?.scan_success_status);
  const dailyTone = kpiTone(qrKpis?.daily_scan_status);
  const trendItems = Array.isArray(trend?.items) ? trend.items : [];
  const trendScope = trend?.variant_id === 'all' ? 'All variants' : trend?.variant_id;

  return (
    <Card className="border-sky-500/20 bg-sky-500/[0.04]">
      <CardHeader className="gap-3 p-4 sm:flex-row sm:items-center sm:justify-between sm:space-y-0 sm:p-6">
        <CardTitle className="text-base flex items-center gap-2">
          <Activity className="h-4 w-4 text-sky-300" />
          Consumer QR KPIs
        </CardTitle>
        <label htmlFor="qr-kpi-reporting-timezone" className="flex items-center gap-2 text-xs text-muted-foreground">
          <Clock3 className="h-3.5 w-3.5 text-sky-300" />
          <span>Reporting day</span>
          <select
            id="qr-kpi-reporting-timezone"
            value={selectedTimezone}
            onChange={(event) => onTimezoneChange(event.target.value)}
            className="min-h-11 max-w-[220px] rounded-md border border-border bg-background px-2 text-xs text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {timezoneOptions.map((timezone) => (
              <option key={timezone} value={timezone}>
                {timezone}
              </option>
            ))}
          </select>
        </label>
      </CardHeader>
      <CardContent className="px-4 pb-4 sm:px-6 sm:pb-6">
        {error && (
          <div
            data-testid="qr-kpi-error"
            className="mb-4 break-words rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-100"
          >
            <span className="font-medium">QR KPI service unavailable:</span>{' '}
            <span title={error} className="select-all">
              {error}
            </span>
          </div>
        )}
        {qrKpis ? (
          <div className="grid gap-3 md:grid-cols-2 md:gap-4">
            <div className={`rounded-lg border p-3 sm:p-4 ${successTone.border} ${successTone.bg}`}>
              <div data-testid="qr-kpi-scan-success-summary" className="flex flex-col items-start gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">QR scan success</p>
                  <p className="mt-1 text-2xl font-bold text-foreground sm:mt-2 sm:text-3xl">{formatPercent(qrKpis.scan_success_rate)}</p>
                </div>
                <Badge data-testid="qr-kpi-scan-success-status" variant={successTone.badge} className="gap-1.5 whitespace-nowrap shrink-0">
                  {successTone.icon}
                  {formatKpiStatus(qrKpis.scan_success_status)}
                </Badge>
              </div>
              <p className="mt-2 text-xs text-muted-foreground sm:mt-3">
                {qrKpis.scan_success_sessions} of {qrKpis.scan_start_sessions} scan sessions reached verification.
                Target {formatPercent(qrKpis.target_scan_success_rate)}.
              </p>
            </div>
            <div className={`rounded-lg border p-3 sm:p-4 ${dailyTone.border} ${dailyTone.bg}`}>
              <div data-testid="qr-kpi-daily-scan-summary" className="flex flex-col items-start gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Consumer scans today</p>
                  <p className="mt-1 text-2xl font-bold text-foreground sm:mt-2 sm:text-3xl">{qrKpis.consumer_scan_sessions}</p>
                </div>
                <Badge data-testid="qr-kpi-daily-scan-status" variant={dailyTone.badge} className="gap-1.5 whitespace-nowrap shrink-0">
                  {dailyTone.icon}
                  {formatKpiStatus(qrKpis.daily_scan_status)}
                </Badge>
              </div>
              <div className="mt-2 h-2 rounded-full bg-black/20 sm:mt-3">
                <div
                  className="h-full rounded-full bg-sky-400"
                  style={{ width: `${Math.round((qrKpis.daily_scan_progress || 0) * 100)}%` }}
                />
              </div>
              <p className="mt-2 text-xs text-muted-foreground sm:mt-3">
                Target {formatDashboardCount(qrKpis.target_daily_scans)} scans in {qrKpis.hours} hours.
              </p>
            </div>
          </div>
        ) : (
          <p className="rounded-md border border-dashed border-border p-4 text-sm text-muted-foreground">
            QR KPI data has not loaded yet.
          </p>
        )}
        {trendItems.length > 0 && (
          <div className="mt-4 border-t border-border pt-3 sm:mt-5 sm:pt-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-medium text-foreground">7-day QR trend</p>
              <span className="text-xs text-muted-foreground">
                {trendScope} / {trend?.timezone || 'UTC'}
              </span>
            </div>
            <div className="mt-3">
              <div
                data-testid="qr-kpi-trend-grid"
                className="grid w-full gap-px overflow-hidden rounded-md border border-border/70 bg-border/70"
                style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(92px, 1fr))' }}
              >
                {trendItems.map((item) => {
                  const tone = kpiTone(item.scan_success_status);
                  const formattedTrendDate = formatTrendDate(item.date);
                  const formattedTrendScans = `${formatDashboardCount(item.verification_complete_sessions)} scans`;
                  return (
                    <div key={item.date} className="min-w-0 bg-background/40 px-3 py-2">
                      <p title={formattedTrendDate} className="truncate select-all text-xs font-medium text-muted-foreground">
                        {formattedTrendDate}
                      </p>
                      <p className={`mt-1 text-sm font-semibold ${tone.text}`}>
                        {formatPercent(item.scan_success_rate)}
                      </p>
                      <p title={formattedTrendScans} className="mt-1 truncate select-all text-xs text-muted-foreground">
                        {formattedTrendScans}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function StatCard({ title, value, icon, color, bg, sub }) {
  return (
    <Card className="hover:shadow-lg hover:shadow-primary/5 transition-shadow">
      <CardContent className="p-6">
        <div className="flex justify-between items-start">
          <div>
            <p className="text-sm font-medium text-muted-foreground">{title}</p>
            <p className="text-3xl font-bold text-foreground mt-2">{value}</p>
            {sub && <p className="text-xs text-muted-foreground mt-1">{sub}</p>}
          </div>
          <div className={`p-3 rounded-xl ${bg} ${color}`}>
            {icon}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function DashboardSkeleton() {
  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      <div className="h-10 w-64 bg-muted animate-pulse rounded-lg" />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {[1, 2, 3, 4].map(i => (
          <Card key={i} className="animate-pulse">
            <CardContent className="p-6 flex justify-between">
              <div className="space-y-4 w-1/2">
                <div className="h-4 bg-muted rounded w-full" />
                <div className="h-8 bg-muted rounded w-3/4" />
              </div>
              <div className="h-12 w-12 bg-muted rounded-xl" />
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {[1, 2].map(i => (
          <Card key={i} className="h-64 animate-pulse" />
        ))}
      </div>
    </div>
  );
}
