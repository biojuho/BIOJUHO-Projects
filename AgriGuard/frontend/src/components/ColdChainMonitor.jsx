import { useState, useEffect, useRef } from 'react';
import { Thermometer, Droplets, AlertTriangle, Activity, Wifi, WifiOff } from 'lucide-react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine } from 'recharts';
import { useToast } from '../contexts/ToastContext';
import { cn } from '../lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from './ui/Card';
import { Badge } from './ui/Badge';

const ZONE_COLORS = {
  'Cold Storage A': '#3b82f6',
  'Cold Storage B': '#8b5cf6',
  'Transport Unit 1': '#f59e0b',
  'Transport Unit 2': '#10b981',
};

export default function ColdChainMonitor() {
  const [readings, setReadings] = useState([]);
  const [status, setStatus] = useState(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const { showToast } = useToast();

  useEffect(() => {
    fetch('/api/iot/status')
      .then((r) => r.json())
      .then(setStatus)
      .catch(() => showToast('IoT status unavailable', 'warning'));

    const wsUrl = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/api/ws/iot`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'history') {
        setReadings(data.data);
      } else {
        setReadings((prev) => [...prev.slice(-100), data]);
        if (data.alerts && data.alerts.length > 0) {
          showToast(data.alerts[0], 'error');
        }
      }
    };

    return () => ws.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const chartData = readings.map((r) => ({
    time: new Date(r.timestamp).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }),
    temp: r.temperature,
    humidity: r.humidity,
    zone: r.zone,
  }));

  const latestReading = readings[readings.length - 1];

  const chartTooltipStyle = {
    backgroundColor: 'hsl(215 28% 11%)',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: '12px',
    color: '#e2e8f0',
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Cold-Chain Monitor</h1>
          <p className="text-sm text-muted-foreground mt-1">실시간 온도·습도 IoT 모니터링</p>
        </div>
        <Badge variant={connected ? 'success' : 'destructive'} className="gap-1.5">
          {connected ? <Wifi className="w-3.5 h-3.5" /> : <WifiOff className="w-3.5 h-3.5" />}
          {connected ? 'Live' : 'Disconnected'}
        </Badge>
      </div>

      {/* Live Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={Thermometer}
          label="Temperature"
          value={latestReading ? `${latestReading.temperature}°C` : '--'}
          color={latestReading?.temperature > 8 || latestReading?.temperature < -25 ? 'red' : 'blue'}
        />
        <StatCard
          icon={Droplets}
          label="Humidity"
          value={latestReading ? `${latestReading.humidity}%` : '--'}
          color="cyan"
        />
        <StatCard
          icon={Activity}
          label="Zone"
          value={latestReading?.zone || '--'}
          color="purple"
        />
        <StatCard
          icon={AlertTriangle}
          label="Alerts"
          value={status?.zones?.reduce((sum, z) => sum + z.alert_count, 0) || 0}
          color={status?.overall_status === 'alert' ? 'red' : 'green'}
        />
      </div>

      {/* Temperature Chart */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Temperature Timeline</CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="time" stroke="#6b7280" fontSize={11} />
              <YAxis stroke="#6b7280" fontSize={11} domain={[-30, 15]} />
              <Tooltip contentStyle={chartTooltipStyle} labelStyle={{ color: '#9ca3af' }} />
              <ReferenceLine y={8} stroke="#ef4444" strokeDasharray="5 5" label={{ value: "Max 8°C", fill: "#ef4444", fontSize: 10 }} />
              <ReferenceLine y={-25} stroke="#3b82f6" strokeDasharray="5 5" label={{ value: "Min -25°C", fill: "#3b82f6", fontSize: 10 }} />
              <Line type="monotone" dataKey="temp" stroke="#60a5fa" strokeWidth={2} dot={false} name="Temperature" />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Humidity Chart */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Humidity Timeline</CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="time" stroke="#6b7280" fontSize={11} />
              <YAxis stroke="#6b7280" fontSize={11} domain={[0, 100]} />
              <Tooltip contentStyle={chartTooltipStyle} labelStyle={{ color: '#9ca3af' }} />
              <Line type="monotone" dataKey="humidity" stroke="#06b6d4" strokeWidth={2} dot={false} name="Humidity" />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Zone Status */}
      {status?.zones && status.zones.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Zone Overview</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {status.zones.map((zone) => (
                <div key={zone.zone} className={cn(
                  'p-4 rounded-xl border',
                  zone.alert_count > 0
                    ? 'border-destructive/30 bg-destructive/5'
                    : 'border-border bg-white/5'
                )}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-foreground">{zone.zone}</span>
                    {zone.alert_count > 0 && (
                      <Badge variant="destructive">{zone.alert_count} alerts</Badge>
                    )}
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-sm">
                    <div>
                      <span className="text-muted-foreground">Avg</span>
                      <p className="text-blue-400 font-mono">{zone.avg_temp}°C</p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Min</span>
                      <p className="text-cyan-400 font-mono">{zone.min_temp}°C</p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Max</span>
                      <p className="text-orange-400 font-mono">{zone.max_temp}°C</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function StatCard({ icon: Icon, label, value, color }) {
  const colorMap = {
    blue: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
    red: 'text-red-400 bg-red-500/10 border-red-500/20',
    green: 'text-primary bg-primary/10 border-primary/20',
    cyan: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20',
    purple: 'text-purple-400 bg-purple-500/10 border-purple-500/20',
  };
  const cls = colorMap[color] || colorMap.blue;

  return (
    <Card className={cn('backdrop-blur-lg', cls)}>
      <CardContent className="p-4">
        <div className="flex items-center gap-2 mb-2">
          <Icon className="w-4 h-4" />
          <span className="text-xs text-muted-foreground">{label}</span>
        </div>
        <p className="text-xl font-bold truncate">{value}</p>
      </CardContent>
    </Card>
  );
}
