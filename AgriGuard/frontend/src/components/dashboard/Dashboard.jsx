import { useState, useEffect } from 'react';
import { Activity, Package, ShieldCheck, Thermometer, AlertTriangle, CheckCircle2, TrendingUp, MapPin } from 'lucide-react';
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
  const maxStatus = Math.max(...statusEntries.map(([, v]) => v), 1);
  const maxOrigin = Math.max(...originEntries.map(([, v]) => v), 1);

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
            <div className="space-y-3">
              {statusEntries.map(([status, count]) => (
                <div key={status}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="font-medium text-slate-600">{status}</span>
                    <span className="text-slate-400">{count}건</span>
                  </div>
                  <div className="h-2.5 w-full bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-emerald-400 to-teal-500 rounded-full transition-all duration-700"
                      style={{ width: `${(count / maxStatus) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
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
            <div className="space-y-3">
              {originEntries.map(([origin, count]) => (
                <div key={origin}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="font-medium text-slate-600">{origin}</span>
                    <span className="text-slate-400">{count}개</span>
                  </div>
                  <div className="h-2.5 w-full bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-blue-400 to-indigo-500 rounded-full transition-all duration-700"
                      style={{ width: `${(count / maxOrigin) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
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
