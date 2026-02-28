import { useState, useEffect } from 'react';
import { Activity, Package, ShieldCheck, Thermometer, AlertTriangle, CheckCircle2, TrendingUp, MapPin } from 'lucide-react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, PieChart, Pie, Cell, Legend } from 'recharts';
import api from '../../services/api';

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.get('/dashboard/summary')
      .then(res => {
        setData(res.data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) return <DashboardSkeleton />;

  if (error) {
    return (
      <div className="p-8 text-center bg-red-50/50 rounded-xl border border-red-100 m-8">
        <AlertTriangle className="mx-auto h-12 w-12 text-red-500 mb-4" />
        <h2 className="text-xl font-semibold text-red-700">백엔드 연결 실패</h2>
        <p className="text-red-500 mt-2 text-sm">AgriGuard 백엔드(포트 8002)가 실행 중인지 확인하세요.</p>
        <p className="text-red-400 mt-1 text-xs font-mono">{error}</p>
      </div>
    );
  }

  const statusDist = data?.status_distribution || {};
  const originDist = data?.origin_distribution || {};
  const statusEntries = Object.entries(statusDist).sort((a, b) => b[1] - a[1]);
  const originEntries = Object.entries(originDist).sort((a, b) => b[1] - a[1]);
  // Data mapping for Recharts
  const statusChartData = statusEntries.map(([name, value]) => ({ name, value }));
  const originChartData = originEntries.map(([name, value]) => ({ name, value }));
  
  // Aesthetically pleasing color palette for PieChart
  const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899', '#f43f5e'];

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold bg-gradient-to-r from-emerald-600 to-teal-400 bg-clip-text text-transparent">
          AgriGuard 공급망 현황
        </h1>
        <div className="flex items-center space-x-2 text-sm text-emerald-600 bg-emerald-50 px-3 py-1.5 rounded-full border border-emerald-100">
          <CheckCircle2 className="h-4 w-4" />
          <span>실시간 데이터</span>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="전체 제품"
          value={data?.total_products ?? 0}
          icon={<Package className="h-5 w-5" />}
          color="text-blue-600"
          bg="bg-blue-50"
        />
        <StatCard
          title="인증 제품"
          value={data?.certified_products ?? 0}
          icon={<ShieldCheck className="h-5 w-5" />}
          color="text-emerald-600"
          bg="bg-emerald-50"
          sub={data?.total_products > 0
            ? `${Math.round((data.certified_products / data.total_products) * 100)}% 인증률`
            : '—'}
        />
        <StatCard
          title="콜드체인 제품"
          value={data?.cold_chain_products ?? 0}
          icon={<Thermometer className="h-5 w-5" />}
          color="text-cyan-600"
          bg="bg-cyan-50"
        />
        <StatCard
          title="추적 이벤트"
          value={data?.total_tracking_events ?? 0}
          icon={<Activity className="h-5 w-5" />}
          color="text-violet-600"
          bg="bg-violet-50"
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Status Distribution */}
        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-6">
          <h2 className="text-base font-semibold text-slate-700 mb-5 flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-emerald-500" />
            추적 상태 분포
          </h2>
          {statusEntries.length === 0 ? (
            <div className="flex items-center justify-center h-40 text-slate-400 text-sm">
              추적 이벤트가 없습니다
            </div>
          ) : (
            <div className="h-64 mt-4">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={statusChartData} layout="vertical" margin={{ top: 5, right: 30, left: 40, bottom: 5 }}>
                  <XAxis type="number" hide />
                  <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 13 }} width={80} />
                  <Tooltip 
                    cursor={{fill: '#f8fafc'}}
                    contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)' }}
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
        </div>

        {/* Origin Distribution */}
        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-6">
          <h2 className="text-base font-semibold text-slate-700 mb-5 flex items-center gap-2">
            <MapPin className="h-4 w-4 text-blue-500" />
            원산지별 제품 현황
          </h2>
          {originEntries.length === 0 ? (
            <div className="flex items-center justify-center h-40 text-slate-400 text-sm">
              제품이 없습니다
            </div>
          ) : (
            <div className="h-64 mt-4">
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
                    contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)' }}
                    itemStyle={{ color: '#334155', fontWeight: 500 }}
                  />
                  <Legend verticalAlign="bottom" height={36} iconType="circle" />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({ title, value, icon, color, bg, sub }) {
  return (
    <div className="p-6 bg-white rounded-2xl border border-slate-100 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex justify-between items-start">
        <div>
          <p className="text-sm font-medium text-slate-500">{title}</p>
          <p className="text-3xl font-bold text-slate-900 mt-2">{value}</p>
          {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
        </div>
        <div className={`p-3 rounded-xl ${bg} ${color}`}>
          {icon}
        </div>
      </div>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      <div className="h-10 w-64 bg-slate-200 animate-pulse rounded-lg" />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {[1, 2, 3, 4].map(i => (
          <div key={i} className="h-32 bg-slate-100 animate-pulse rounded-2xl border border-slate-100 p-6 flex justify-between">
            <div className="space-y-4 w-1/2">
              <div className="h-4 bg-slate-200 rounded w-full" />
              <div className="h-8 bg-slate-200 rounded w-3/4" />
            </div>
            <div className="h-12 w-12 bg-slate-200 rounded-xl" />
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {[1, 2].map(i => (
          <div key={i} className="h-64 bg-slate-100 animate-pulse rounded-2xl border border-slate-100" />
        ))}
      </div>
    </div>
  );
}
