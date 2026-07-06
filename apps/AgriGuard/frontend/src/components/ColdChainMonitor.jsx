import { useState, useEffect, useRef, useCallback } from 'react';
import { Thermometer, Droplets, AlertTriangle, Activity, Wifi, WifiOff, Clock, ServerCrash } from 'lucide-react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine } from 'recharts';
import { useToast } from '../contexts/ToastContext';
import { cn } from '../lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from './ui/Card';
import { Badge } from './ui/Badge';
import { useThrottledWebSocket } from '../hooks/useThrottledWebSocket';

const STATUS_POLL_INTERVAL_MS = 15000;
const COLD_CHAIN_LOCALE = 'en-US';

const CONNECTIVITY_LABELS = {
  online: 'Sensors online',
  stale: 'Sensor delay',
  offline: 'Sensor offline',
  no_data: 'No sensor data',
};

const CONNECTIVITY_VARIANTS = {
  online: 'success',
  stale: 'warning',
  offline: 'destructive',
  no_data: 'secondary',
};

const formatTemperature = (value, fallback = '--') => (
  typeof value === 'number' ? `${value} C` : fallback
);

const formatHumidity = (value, fallback = '--') => (
  typeof value === 'number' ? `${value}%` : fallback
);

const formatLastSeen = (value) => {
  if (!value) {
    return 'No readings';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return 'Unknown';
  }

  return new Intl.DateTimeFormat(COLD_CHAIN_LOCALE, {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    timeZoneName: 'short',
  }).format(date);
};

function getSensorStatusMessage({ connectivityStatus, offlineSensors, staleSensors, deviceCount, watchHours }) {
  if (connectivityStatus === 'offline') {
    return `${offlineSensors} offline and ${staleSensors} stale across ${deviceCount} devices`;
  }
  if (connectivityStatus === 'stale') {
    return `${staleSensors} stale across ${deviceCount} devices`;
  }
  if (connectivityStatus === 'no_data') {
    return `No device check-ins in the ${watchHours} hour watch window`;
  }
  return `${deviceCount} devices reporting inside the expected window`;
}

function getAttentionClass(connectivityStatus) {
  if (connectivityStatus === 'offline') {
    return 'border-destructive/30 bg-destructive/10 text-destructive';
  }
  return 'border-amber-500/30 bg-amber-500/10 text-amber-300';
}

function getZoneClass(zone) {
  if (zone.connectivity_status === 'offline' || zone.alert_count > 0) {
    return 'border-destructive/30 bg-destructive/5';
  }
  if (zone.connectivity_status === 'stale') {
    return 'border-amber-500/30 bg-amber-500/5';
  }
  return 'border-border bg-white/5';
}

function EmptyTimelineState({ title, message, heightClass }) {
  return (
    <div
      role="status"
      aria-atomic="true"
      className={cn(
        'flex flex-col items-center justify-center rounded-lg border border-dashed border-border bg-background/40 px-4 text-center',
        heightClass,
      )}
    >
      <p className="text-sm font-semibold text-foreground">{title}</p>
      <p className="mt-1 max-w-xs text-sm leading-6 text-muted-foreground">{message}</p>
    </div>
  );
}

export default function ColdChainMonitor() {
  const [status, setStatus] = useState(null);
  const [statusError, setStatusError] = useState('');
  const { showToast } = useToast();

  const wsUrl = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/api/ws/iot`;
  const { data: readings, connected } = useThrottledWebSocket(wsUrl, {
    throttleMs: 150,
    maxItems: 200,
    onAlert: (alert) => showToast(alert, 'error'),
  });
  const prevConnectedRef = useRef(connected);

  const fetchStatus = useCallback((signal) => {
    return fetch('/api/iot/status', { signal })
      .then((r) => {
        if (!r.ok) {
          throw new Error(`IoT status request failed: ${r.status}`);
        }
        return r.json();
      })
      .then((payload) => {
        setStatus(payload);
        setStatusError('');
      })
      .catch((error) => {
        if (error?.name === 'AbortError') {
          return;
        }
        setStatusError('IoT aggregate status is unavailable. Live stream readings may still arrive, but zone health is delayed.');
      });
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void fetchStatus(controller.signal);

    const intervalId = window.setInterval(() => {
      void fetchStatus();
    }, STATUS_POLL_INTERVAL_MS);

    return () => {
      controller.abort();
      window.clearInterval(intervalId);
    };
  }, [fetchStatus]);

  useEffect(() => {
    if (connected && !prevConnectedRef.current) {
      void fetchStatus();
    }
    prevConnectedRef.current = connected;
  }, [connected, fetchStatus]);

  const chartData = readings.map((r) => ({
    time: new Intl.DateTimeFormat(COLD_CHAIN_LOCALE, { hour: '2-digit', minute: '2-digit' }).format(new Date(r.timestamp)),
    temp: r.temperature,
    humidity: r.humidity,
    zone: r.zone,
  }));
  const hasTimelineReadings = chartData.length > 0;

  const latestReading = readings[readings.length - 1];
  const zones = status?.zones ?? [];
  const alertCount = zones.reduce((sum, zone) => sum + (zone.alert_count || 0), 0);
  const staleSensors = status?.stale_sensor_count ?? zones.reduce((sum, zone) => sum + (zone.stale_count || 0), 0);
  const offlineSensors = status?.offline_sensor_count ?? zones.reduce((sum, zone) => sum + (zone.offline_count || 0), 0);
  const deviceCount = status?.device_count ?? zones.reduce((sum, zone) => sum + (zone.device_count || 0), 0);
  const connectivityStatus = status?.connectivity_status || (connected ? 'online' : 'offline');
  const connectivityLabel = CONNECTIVITY_LABELS[connectivityStatus] ?? connectivityStatus;
  const connectivityVariant = CONNECTIVITY_VARIANTS[connectivityStatus] ?? 'secondary';
  const hasSensorAttention = ['offline', 'stale', 'no_data'].includes(connectivityStatus);
  const sensorStatusMessage = getSensorStatusMessage({
    connectivityStatus,
    offlineSensors,
    staleSensors,
    deviceCount,
    watchHours: status?.device_watch_hours ?? 24,
  });

  const chartTooltipStyle = {
    backgroundColor: 'hsl(215 28% 11%)',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: '12px',
    color: '#e2e8f0',
  };

  return (
    <div className="space-y-5 sm:space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Cold-Chain Monitor</h1>
          <p className="mt-1 text-sm text-muted-foreground">Real-time IoT temperature, humidity, and sensor health</p>
        </div>
        <div className="flex flex-wrap justify-start gap-2 sm:justify-end">
          <Badge variant={connectivityVariant} className="gap-1.5">
            {connectivityStatus === 'offline' ? <ServerCrash className="h-3.5 w-3.5" /> : <Clock className="h-3.5 w-3.5" />}
            {connectivityLabel}
          </Badge>
          <Badge variant={connected ? 'success' : 'destructive'} className="gap-1.5">
            {connected ? <Wifi className="h-3.5 w-3.5" /> : <WifiOff className="h-3.5 w-3.5" />}
            {connected ? 'Stream live' : 'Stream disconnected'}
          </Badge>
        </div>
      </div>

      {hasSensorAttention && (
        <div
          role="status"
          aria-atomic="true"
          className={cn('flex items-start gap-3 rounded-lg border p-3 sm:p-4', getAttentionClass(connectivityStatus))}
        >
          {connectivityStatus === 'offline' ? <ServerCrash className="mt-0.5 h-5 w-5 shrink-0" /> : <Clock className="mt-0.5 h-5 w-5 shrink-0" />}
          <div>
            <p className="font-semibold">{connectivityLabel}</p>
            <p className="text-sm text-muted-foreground">{sensorStatusMessage}</p>
          </div>
        </div>
      )}

      {statusError && (
        <div
          role="status"
          aria-atomic="true"
          className="flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-amber-200 sm:p-4"
        >
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
          <div>
            <p className="font-semibold">IoT status unavailable</p>
            <p className="text-sm text-muted-foreground">{statusError}</p>
          </div>
        </div>
      )}

      <div data-testid="cold-chain-stat-grid" className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-3 xl:grid-cols-5">
        <StatCard
          icon={Thermometer}
          label="Temperature"
          value={formatTemperature(latestReading?.temperature, 'No readings')}
          color={latestReading?.temperature > 8 || latestReading?.temperature < -25 ? 'red' : 'blue'}
        />
        <StatCard
          icon={Droplets}
          label="Humidity"
          value={formatHumidity(latestReading?.humidity, 'No readings')}
          color="cyan"
        />
        <StatCard
          icon={Activity}
          label="Zone"
          value={latestReading?.zone || 'No zone'}
          color="purple"
        />
        <StatCard
          icon={AlertTriangle}
          label="Alerts"
          value={alertCount}
          color={status?.overall_status === 'alert' ? 'red' : 'green'}
        />
        <StatCard
          icon={Clock}
          label="Sensor Health"
          value={`${offlineSensors} offline / ${staleSensors} stale`}
          color={offlineSensors > 0 ? 'red' : staleSensors > 0 ? 'amber' : 'green'}
          className="col-span-2 lg:col-span-1"
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Temperature Timeline</CardTitle>
        </CardHeader>
        <CardContent>
          {hasTimelineReadings ? (
            <ResponsiveContainer width="100%" height={280}>
              <LineChart
                data={chartData}
                title="Temperature timeline chart"
                desc="Keyboard-navigable line chart of recent cold-chain temperature readings with max and min threshold markers."
              >
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="time" stroke="#6b7280" fontSize={11} />
                <YAxis stroke="#6b7280" fontSize={11} domain={[-30, 15]} />
                <Tooltip contentStyle={chartTooltipStyle} labelStyle={{ color: '#9ca3af' }} />
                <ReferenceLine y={8} stroke="#ef4444" strokeDasharray="5 5" label={{ value: 'Max 8 C', fill: '#ef4444', fontSize: 10 }} />
                <ReferenceLine y={-25} stroke="#3b82f6" strokeDasharray="5 5" label={{ value: 'Min -25 C', fill: '#3b82f6', fontSize: 10 }} />
                <Line type="monotone" dataKey="temp" stroke="#60a5fa" strokeWidth={2} dot={false} name="Temperature" />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <EmptyTimelineState
              title="No temperature readings yet"
              message="Waiting for live sensor readings from registered cold-chain devices."
              heightClass="h-[280px]"
            />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Humidity Timeline</CardTitle>
        </CardHeader>
        <CardContent>
          {hasTimelineReadings ? (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart
                data={chartData}
                title="Humidity timeline chart"
                desc="Keyboard-navigable line chart of recent cold-chain humidity readings."
              >
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="time" stroke="#6b7280" fontSize={11} />
                <YAxis stroke="#6b7280" fontSize={11} domain={[0, 100]} />
                <Tooltip contentStyle={chartTooltipStyle} labelStyle={{ color: '#9ca3af' }} />
                <Line type="monotone" dataKey="humidity" stroke="#06b6d4" strokeWidth={2} dot={false} name="Humidity" />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <EmptyTimelineState
              title="No humidity readings yet"
              message="Waiting for live humidity readings from registered cold-chain devices."
              heightClass="h-[200px]"
            />
          )}
        </CardContent>
      </Card>

      {status && zones.length === 0 && (
        <Card>
          <CardContent className="p-6">
            <div role="status" aria-atomic="true" className="flex items-center gap-3 text-muted-foreground">
              <ServerCrash className="h-5 w-5" />
              <span>No cold-chain zones have reported inside the current watch window.</span>
            </div>
          </CardContent>
        </Card>
      )}

      {zones.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Zone Overview</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {zones.map((zone) => (
                <div key={zone.zone} className={cn('rounded-xl border p-4', getZoneClass(zone))}>
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <span className="font-medium text-foreground">{zone.zone}</span>
                    <div className="flex flex-wrap justify-end gap-2">
                      <Badge variant={CONNECTIVITY_VARIANTS[zone.connectivity_status] ?? 'secondary'}>
                        {CONNECTIVITY_LABELS[zone.connectivity_status] ?? zone.connectivity_status}
                      </Badge>
                      {zone.alert_count > 0 && (
                        <Badge variant="destructive">{zone.alert_count} alerts</Badge>
                      )}
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-sm">
                    <div>
                      <span className="text-muted-foreground">Avg</span>
                      <p className="font-mono text-blue-400">{formatTemperature(zone.avg_temp)}</p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Min</span>
                      <p className="font-mono text-cyan-400">{formatTemperature(zone.min_temp)}</p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Max</span>
                      <p className="font-mono text-orange-400">{formatTemperature(zone.max_temp)}</p>
                    </div>
                  </div>
                  <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <span className="text-muted-foreground">Sensors</span>
                      <p className="font-mono text-foreground">{zone.device_count || 0} total</p>
                      <p className="text-xs text-muted-foreground">
                        {zone.offline_count || 0} offline / {zone.stale_count || 0} stale
                      </p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Last seen</span>
                      <p className="font-mono text-foreground">{formatLastSeen(zone.latest_seen_at)}</p>
                      <p className="text-xs text-muted-foreground">{zone.readings_count || 0} readings</p>
                    </div>
                  </div>
                  {zone.sensors?.length > 0 && (
                    <ul className="mt-4 space-y-2">
                      {zone.sensors.slice(0, 3).map((sensor) => (
                        <li
                          key={sensor.sensor_id}
                          data-testid="cold-chain-zone-sensor-row"
                          className="flex flex-col items-start gap-2 rounded-md bg-black/10 px-3 py-2 text-sm sm:flex-row sm:items-center sm:justify-between sm:gap-3"
                        >
                          <span
                            data-testid="cold-chain-zone-sensor-id"
                            title={sensor.sensor_id}
                            className="w-full min-w-0 truncate select-all font-mono text-foreground sm:w-auto"
                          >
                            {sensor.sensor_id}
                          </span>
                          <div
                            data-testid="cold-chain-zone-sensor-status"
                            className="flex w-full items-center justify-between gap-2 sm:w-auto sm:shrink-0 sm:justify-end"
                          >
                            <Badge variant={CONNECTIVITY_VARIANTS[sensor.status] ?? 'secondary'}>{sensor.status}</Badge>
                            <span className="font-mono text-xs text-muted-foreground">{sensor.age_minutes}m</span>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function getStatId(label) {
  return label.toLowerCase().replace(/[^a-z0-9]+/g, '-');
}

function StatCard({ icon: Icon, label, value, color, className }) {
  const colorMap = {
    blue: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
    red: 'text-red-400 bg-red-500/10 border-red-500/20',
    green: 'text-primary bg-primary/10 border-primary/20',
    amber: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    cyan: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20',
    purple: 'text-purple-400 bg-purple-500/10 border-purple-500/20',
  };
  const cls = colorMap[color] || colorMap.blue;

  return (
    <Card data-testid={`cold-chain-stat-card-${getStatId(label)}`} className={cn('backdrop-blur-lg', cls, className)}>
      <CardContent className="p-3 sm:p-4">
        <div className="mb-1.5 flex items-center gap-2 sm:mb-2">
          <Icon className="h-4 w-4" />
          <span className="text-xs text-muted-foreground">{label}</span>
        </div>
        <p
          data-testid={`cold-chain-stat-${getStatId(label)}`}
          className="min-h-8 text-wrap break-words text-lg font-bold leading-tight sm:min-h-12 sm:text-xl"
        >
          {value}
        </p>
      </CardContent>
    </Card>
  );
}
