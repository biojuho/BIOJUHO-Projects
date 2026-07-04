import { useState, useEffect } from 'react';
import { Activity, Package, ShieldCheck, Thermometer, AlertTriangle, CheckCircle2, TrendingUp, MapPin, Clock3 } from 'lucide-react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, PieChart, Pie, Cell, Legend } from 'recharts';
import api, { withOperatorAuth } from '../../services/api';
import { useToast } from '../../contexts/ToastContext';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { Badge } from '../ui/Badge';

const QR_KPI_TIMEZONE_STORAGE_KEY = 'agriguard.qrKpi.reportingTimezone';
const DEFAULT_REPORTING_TIMEZONES = ['UTC', 'Asia/Seoul', 'America/Los_Angeles', 'Europe/Amsterdam'];

function getDashboardLoadError(error) {
  const detail = error?.message || 'Dashboard summary could not be loaded.';

  if (error?.response?.status === 401) {
    return {
      title: 'Operator authentication required',
      description: 'Save a Firebase/operator token in QR Tokens or Sensors, then reload the dashboard.',
      toast: 'Operator authentication required for dashboard metrics.',
      detail,
    };
  }

  return {
    title: '백엔드 연결 실패',
    description: 'AgriGuard 백엔드(포트 8002)가 실행 중인지 확인하세요.',
    toast: '백엔드 연결 실패: 포트 8002 서버를 확인해주세요.',
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

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [qrKpis, setQrKpis] = useState(null);
  const [qrKpiTrend, setQrKpiTrend] = useState(null);
  const [qrKpiTimezone, setQrKpiTimezone] = useState(getInitialReportingTimezone);
  const [qrKpiError, setQrKpiError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const { showToast } = useToast();

  useEffect(() => {
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
          <p className="text-muted-foreground mt-1 text-xs font-mono">{error.detail}</p>
        </CardContent>
      </Card>
    );
  }

  const statusDist = data?.status_distribution || {};
  const originDist = data?.origin_distribution || {};
  const statusEntries = Object.entries(statusDist).sort((a, b) => b[1] - a[1]);
  const originEntries = Object.entries(originDist).sort((a, b) => b[1] - a[1]);
  const statusChartData = statusEntries.map(([name, value]) => ({ name, value }));
  const originChartData = originEntries.map(([name, value]) => ({ name, value }));

  const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899', '#f43f5e'];

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold bg-gradient-to-r from-primary to-emerald-600 bg-clip-text text-transparent">
          AgriGuard 공급망 현황
        </h1>
        <Badge variant="success" className="gap-1.5">
          <CheckCircle2 className="h-3.5 w-3.5" />
          실시간 데이터
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
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="전체 제품"
          value={data?.total_products ?? 0}
          icon={<Package className="h-5 w-5" />}
          color="text-blue-400"
          bg="bg-blue-500/15"
        />
        <StatCard
          title="인증 제품"
          value={data?.certified_products ?? 0}
          icon={<ShieldCheck className="h-5 w-5" />}
          color="text-primary"
          bg="bg-primary/15"
          sub={data?.total_products > 0
            ? `${Math.round((data.certified_products / data.total_products) * 100)}% 인증률`
            : '—'}
        />
        <StatCard
          title="콜드체인 제품"
          value={data?.cold_chain_products ?? 0}
          icon={<Thermometer className="h-5 w-5" />}
          color="text-cyan-400"
          bg="bg-cyan-500/15"
        />
        <StatCard
          title="추적 이벤트"
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
              추적 상태 분포
            </CardTitle>
          </CardHeader>
          <CardContent>
            {statusEntries.length === 0 ? (
              <div className="flex items-center justify-center h-40 text-muted-foreground text-sm">
                추적 이벤트가 없습니다
              </div>
            ) : (
              <div className="h-64 min-w-0">
                <ResponsiveContainer width="100%" height={256} minWidth={320}>
                  <BarChart data={statusChartData} layout="vertical" margin={{ top: 5, right: 30, left: 40, bottom: 5 }}>
                    <XAxis type="number" hide />
                    <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 13 }} width={80} />
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
              원산지별 제품 현황
            </CardTitle>
          </CardHeader>
          <CardContent>
            {originEntries.length === 0 ? (
              <div className="flex items-center justify-center h-40 text-muted-foreground text-sm">
                제품이 없습니다
              </div>
            ) : (
              <div className="h-64 min-w-0">
                <ResponsiveContainer width="100%" height={256} minWidth={320}>
                  <PieChart>
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

function formatTrendDate(date) {
  const parsed = new Date(`${date}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return date;
  return parsed.toLocaleDateString(undefined, { month: 'short', day: '2-digit', timeZone: 'UTC' });
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
      <CardHeader className="gap-4 sm:flex-row sm:items-center sm:justify-between sm:space-y-0">
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
            className="h-8 max-w-[220px] rounded-md border border-border bg-background px-2 text-xs text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {timezoneOptions.map((timezone) => (
              <option key={timezone} value={timezone}>
                {timezone}
              </option>
            ))}
          </select>
        </label>
      </CardHeader>
      <CardContent>
        {error && (
          <div className="mb-4 rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-100">
            QR KPI service unavailable: {error}
          </div>
        )}
        {qrKpis ? (
          <div className="grid gap-4 md:grid-cols-2">
            <div className={`rounded-lg border p-4 ${successTone.border} ${successTone.bg}`}>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">QR scan success</p>
                  <p className="mt-2 text-3xl font-bold text-foreground">{formatPercent(qrKpis.scan_success_rate)}</p>
                </div>
                <Badge variant={successTone.badge} className="gap-1.5">
                  {successTone.icon}
                  {formatKpiStatus(qrKpis.scan_success_status)}
                </Badge>
              </div>
              <p className="mt-3 text-xs text-muted-foreground">
                {qrKpis.scan_success_sessions} of {qrKpis.scan_start_sessions} scan sessions reached verification.
                Target {formatPercent(qrKpis.target_scan_success_rate)}.
              </p>
            </div>
            <div className={`rounded-lg border p-4 ${dailyTone.border} ${dailyTone.bg}`}>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Consumer scans today</p>
                  <p className="mt-2 text-3xl font-bold text-foreground">{qrKpis.consumer_scan_sessions}</p>
                </div>
                <Badge variant={dailyTone.badge} className="gap-1.5">
                  {dailyTone.icon}
                  {formatKpiStatus(qrKpis.daily_scan_status)}
                </Badge>
              </div>
              <div className="mt-3 h-2 rounded-full bg-black/20">
                <div
                  className="h-full rounded-full bg-sky-400"
                  style={{ width: `${Math.round((qrKpis.daily_scan_progress || 0) * 100)}%` }}
                />
              </div>
              <p className="mt-3 text-xs text-muted-foreground">
                Target {qrKpis.target_daily_scans.toLocaleString()} scans in {qrKpis.hours} hours.
              </p>
            </div>
          </div>
        ) : (
          <p className="rounded-md border border-dashed border-border p-4 text-sm text-muted-foreground">
            QR KPI data has not loaded yet.
          </p>
        )}
        {trendItems.length > 0 && (
          <div className="mt-5 border-t border-border pt-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-medium text-foreground">7-day QR trend</p>
              <span className="text-xs text-muted-foreground">
                {trendScope} / {trend?.timezone || 'UTC'}
              </span>
            </div>
            <div className="mt-3 overflow-x-auto">
              <div
                className="grid min-w-[680px] overflow-hidden rounded-md border border-border/70"
                style={{ gridTemplateColumns: `repeat(${trendItems.length}, minmax(88px, 1fr))` }}
              >
                {trendItems.map((item) => {
                  const tone = kpiTone(item.scan_success_status);
                  return (
                    <div key={item.date} className="min-w-0 border-l border-border/70 px-3 py-2 first:border-l-0">
                      <p className="truncate text-xs font-medium text-muted-foreground">{formatTrendDate(item.date)}</p>
                      <p className={`mt-1 text-sm font-semibold ${tone.text}`}>
                        {formatPercent(item.scan_success_rate)}
                      </p>
                      <p className="mt-1 truncate text-xs text-muted-foreground">
                        {item.verification_complete_sessions.toLocaleString()} scans
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
