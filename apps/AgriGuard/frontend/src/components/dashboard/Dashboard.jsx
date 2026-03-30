import { useState, useEffect } from 'react';
import { Activity, Package, ShieldCheck, Thermometer, AlertTriangle, CheckCircle2, TrendingUp, MapPin } from 'lucide-react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, PieChart, Pie, Cell, Legend } from 'recharts';
import api from '../../services/api';
import { useToast } from '../../contexts/ToastContext';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { Badge } from '../ui/Badge';

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const { showToast } = useToast();

  useEffect(() => {
    api.get('/dashboard/summary')
      .then(res => {
        setData(res.data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
        showToast('백엔드 연결 실패: 포트 8002 서버를 확인해주세요.', 'error');
      });
  }, [showToast]);

  if (loading) return <DashboardSkeleton />;

  if (error) {
    return (
      <Card className="m-8 border-destructive/30 bg-destructive/5">
        <CardContent className="p-8 text-center">
          <AlertTriangle className="mx-auto h-12 w-12 text-destructive mb-4" />
          <h2 className="text-xl font-semibold text-destructive">백엔드 연결 실패</h2>
          <p className="text-destructive/70 mt-2 text-sm">AgriGuard 백엔드(포트 8002)가 실행 중인지 확인하세요.</p>
          <p className="text-muted-foreground mt-1 text-xs font-mono">{error}</p>
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
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
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
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
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
