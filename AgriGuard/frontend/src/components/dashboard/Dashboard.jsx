import React, { useState, useEffect } from 'react';
import { Activity, Droplets, ThermometerSun, AlertTriangle, CheckCircle2 } from 'lucide-react';

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    // 1.5 seconds delay to show Skeleton UI
    const timer = setTimeout(() => {
      fetch('http://localhost:8000/api/v1/dashboard/summary')
        .then(res => {
          if (!res.ok) throw new Error('API Timeout');
          return res.json();
        })
        .then(json => {
          setData(json.data);
          setLoading(false);
        })
        .catch(err => {
          setError(err.message);
          setLoading(false);
          // Fallback static mock data if Backend is down
          setData({
            total_farms: 142,
            active_sensors: 450,
            critical_alerts: 3,
            growth_cycles: { active: 25, completed: 102 }
          });
        });
    }, 1500);
    return () => clearTimeout(timer);
  }, []);

  if (loading) return <DashboardSkeleton />;
  if (error) {
     return (
       <div className="p-8 text-center bg-red-50/50 rounded-xl border border-red-100 m-8">
         <AlertTriangle className="mx-auto h-12 w-12 text-red-500 mb-4" />
         <h2 className="text-xl font-semibold text-red-700">Failed to load live data</h2>
         <p className="text-red-500 mt-2">Displaying cached offline data instead.</p>
       </div>
     )
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 animate-in fade-in duration-500">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold bg-gradient-to-r from-emerald-600 to-teal-400 bg-clip-text text-transparent">
          AgriGuard Overview
        </h1>
        <div className="flex items-center space-x-2 text-sm text-emerald-600 bg-emerald-50 px-3 py-1.5 rounded-full border border-emerald-100">
          <CheckCircle2 className="h-4 w-4" />
          <span>System Stable</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard title="Active Sensors" value={data?.active_sensors} icon={<Activity className="h-5 w-5" />} color="text-blue-500" bg="bg-blue-50" />
        <StatCard title="Total Farms" value={data?.total_farms} icon={<ThermometerSun className="h-5 w-5" />} color="text-amber-500" bg="bg-amber-50" />
        <StatCard title="Critical Alerts" value={data?.critical_alerts} icon={<AlertTriangle className="h-5 w-5" />} color="text-red-500" bg="bg-red-50" />
        <StatCard title="Growth Cycles" value={data?.growth_cycles.active} icon={<Droplets className="h-5 w-5" />} color="text-emerald-500" bg="bg-emerald-50" />
      </div>
      
      {/* Temporary Placeholder for Chart Area */}
      <div className="h-96 w-full bg-white rounded-2xl border border-slate-100 shadow-sm flex items-center justify-center">
         <p className="text-slate-400 font-medium">Data Visualization Area</p>
      </div>
    </div>
  );
}

function StatCard({ title, value, icon, color, bg }) {
  return (
    <div className="p-6 bg-white rounded-2xl border border-slate-100 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex justify-between items-start">
        <div>
          <p className="text-sm font-medium text-slate-500">{title}</p>
          <p className="text-3xl font-bold text-slate-900 mt-2">{value}</p>
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
      <div className="h-96 w-full bg-slate-100 animate-pulse rounded-2xl border border-slate-100" />
    </div>
  )
}
