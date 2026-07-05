import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  Battery,
  CheckCircle2,
  Clock,
  Copy,
  Download,
  FileText,
  Fingerprint,
  History,
  KeyRound,
  Loader2,
  MapPin,
  Pencil,
  Plus,
  Power,
  RadioTower,
  RefreshCw,
  Save,
  Search,
  ShieldAlert,
  ShieldCheck,
  Terminal,
  Wifi,
  WifiOff,
} from 'lucide-react';
import { sensorDeviceAdminApi, getOperatorToken, setOperatorToken } from '../services/api';
import { Badge } from './ui/Badge';
import { Button } from './ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/Card';
import { Input } from './ui/Input';
import { cn } from '../lib/utils';

const PAGE_SIZE = 20;
const REJECTION_PAGE_SIZE = 10;
const PROVISIONING_EVIDENCE_PAGE_SIZE = 5;
const STATUS_OPTIONS = ['all', 'active', 'disabled'];
const REJECTION_REASON_OPTIONS = ['all', 'unregistered_sensor', 'disabled_sensor', 'authorization_check_failed'];
const SENSOR_ID_PATTERN = '[A-Za-z0-9_.:\\-]+';
const SENSOR_ID_PATTERN_RE = /^[A-Za-z0-9_.:-]+$/;
const SENSOR_ID_PATTERN_MESSAGE = 'Sensor ID may contain letters, numbers, dot, underscore, colon, and hyphen.';
const PROTECTED_AUTO_LOAD_MESSAGE = 'Save an operator bearer token to load protected sensor data.';
const DEFAULT_PROVISIONING_CONFIG = {
  passwordFilePath: '/etc/mosquitto/passwd',
  dynamicSecurityRole: 'agriguard-sensor',
};
const EMPTY_FORM = {
  sensorId: '',
  label: '',
  zone: '',
  ownerId: '',
  clearOwner: false,
  expectedIntervalMinutes: '5',
  isActive: true,
};

function formatDateTime(value) {
  if (!value) return 'Never seen';
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

function formatBattery(value) {
  if (value === null || value === undefined) return 'No reading';
  return `${Math.round(Number(value))}%`;
}

function formatStatusLabel(value) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function formatReasonLabel(value) {
  if (!value) return 'Unknown';
  return value.replaceAll('_', ' ');
}

function isBrokerSafeSensorId(value) {
  return SENSOR_ID_PATTERN_RE.test(String(value || '').trim());
}

function formatDisabledCount(count) {
  return `${count} unsupported sensor ID${count === 1 ? '' : 's'} disabled.`;
}

function commandLinesText(lines, emptyLabel = '# none') {
  return Array.isArray(lines) && lines.length > 0 ? lines.join('\n') : emptyLabel;
}

function formatProvisioningBundle(provisioning) {
  if (!provisioning) return '';
  const generatedAt = formatDateTime(provisioning.generated_at);
  const notes = Array.isArray(provisioning.notes) && provisioning.notes.length > 0
    ? provisioning.notes.map((note) => `- ${note}`).join('\n')
    : '- No notes returned.';
  const unsupported = Array.isArray(provisioning.unsupported_sensor_ids) && provisioning.unsupported_sensor_ids.length > 0
    ? provisioning.unsupported_sensor_ids.join('\n')
    : '# none';

  return [
    '# AgriGuard MQTT broker provisioning',
    `# Generated at: ${generatedAt}`,
    `# Active sensors: ${provisioning.active_sensor_count ?? 0}`,
    `# Disabled sensors: ${provisioning.disabled_sensor_count ?? 0}`,
    '',
    '## mosquitto ACL file',
    provisioning.acl_file || '# empty ACL file',
    '## mosquitto_passwd create/update commands',
    commandLinesText(provisioning.password_file_commands),
    '',
    '## mosquitto_passwd delete commands',
    commandLinesText(provisioning.password_file_delete_commands),
    '',
    '## Mosquitto dynamic-security commands',
    commandLinesText(provisioning.dynamic_security_commands),
    '',
    '## Unsupported sensor IDs',
    unsupported,
    '',
    '## Notes',
    notes,
    '',
  ].join('\n');
}

function downloadTextFile(filename, text) {
  if (typeof document === 'undefined') return;
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function sha256Hex(text) {
  if (!globalThis.crypto?.subtle) {
    throw new Error('SHA-256 hashing is not available in this browser context.');
  }
  const encoded = new TextEncoder().encode(text);
  const digest = await globalThis.crypto.subtle.digest('SHA-256', encoded);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
}

function SensorStateBadge({ isActive }) {
  return (
    <Badge variant={isActive ? 'success' : 'warning'} className="gap-1.5">
      {isActive ? <Wifi className="h-3.5 w-3.5" /> : <WifiOff className="h-3.5 w-3.5" />}
      {isActive ? 'Active' : 'Disabled'}
    </Badge>
  );
}

function RegistryGateBadge({ isRequired }) {
  return (
    <Badge variant={isRequired ? 'info' : 'outline'} className="gap-1.5">
      {isRequired ? <WifiOff className="h-3.5 w-3.5" /> : <Wifi className="h-3.5 w-3.5" />}
      {isRequired ? 'Required' : 'Bypassed'}
    </Badge>
  );
}

function SensorStat({ label, value }) {
  return (
    <div className="rounded-lg border border-border bg-white/[0.03] px-3 py-2.5 sm:px-4 sm:py-3">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-xl font-semibold text-foreground sm:text-2xl">{value}</p>
    </div>
  );
}

export default function SensorDeviceManager() {
  const actionStatusRef = useRef(null);
  const [operatorTokenInput, setOperatorTokenInput] = useState(() => getOperatorToken());
  const [hasSavedOperatorToken, setHasSavedOperatorToken] = useState(() => Boolean(getOperatorToken()));
  const [draftStatus, setDraftStatus] = useState('all');
  const [draftZone, setDraftZone] = useState('');
  const [sensorStatus, setSensorStatus] = useState('all');
  const [zoneFilter, setZoneFilter] = useState('');
  const [page, setPage] = useState(1);
  const [rejectionPage, setRejectionPage] = useState(1);
  const [rejectionDraft, setRejectionDraft] = useState({
    windowHours: '24',
    sensorId: '',
    reason: 'all',
  });
  const [rejectionFilter, setRejectionFilter] = useState({
    windowHours: 24,
    sensorId: '',
    reason: 'all',
  });
  const [formState, setFormState] = useState(EMPTY_FORM);
  const [deviceState, setDeviceState] = useState({
    loading: false,
    error: null,
    data: null,
  });
  const [provisioningDraft, setProvisioningDraft] = useState(DEFAULT_PROVISIONING_CONFIG);
  const [provisioningState, setProvisioningState] = useState({
    loading: false,
    error: null,
    data: null,
  });
  const [provisioningEvidenceState, setProvisioningEvidenceState] = useState({
    loading: false,
    error: null,
    data: null,
  });
  const [provisioningEvidenceHistoryState, setProvisioningEvidenceHistoryState] = useState({
    loading: false,
    error: null,
    data: null,
  });
  const [evidenceHistoryFilter, setEvidenceHistoryFilter] = useState({ brokerHost: '' });
  const [evidenceHistoryDraft, setEvidenceHistoryDraft] = useState({ brokerHost: '' });
  const [evidenceHistoryPage, setEvidenceHistoryPage] = useState(1);
  const [evidenceDraft, setEvidenceDraft] = useState({
    mode: 'combined',
    brokerHost: '',
    runbookReference: '',
    credentialsRotated: true,
    rotationNote: '',
  });
  const [unsupportedState, setUnsupportedState] = useState({
    loading: false,
    error: null,
    data: null,
  });
  const [reissueDrafts, setReissueDrafts] = useState({});
  const [reissuePendingId, setReissuePendingId] = useState(null);
  const [actionState, setActionState] = useState({
    loading: false,
    error: null,
    success: null,
  });
  const [rejectionState, setRejectionState] = useState({
    loading: false,
    error: null,
    data: null,
  });
  const [pendingSensorId, setPendingSensorId] = useState(null);

  const fetchDevices = useCallback(async ({ status, zone, nextPage } = {}) => {
    const requestedStatus = status ?? sensorStatus;
    const requestedZone = zone ?? zoneFilter;
    const requestedPage = nextPage ?? page;

    setDeviceState((current) => ({ ...current, loading: true, error: null }));
    try {
      const response = await sensorDeviceAdminApi.list({
        sensorStatus: requestedStatus,
        zone: requestedZone,
        page: requestedPage,
        pageSize: PAGE_SIZE,
      });
      setDeviceState({ loading: false, error: null, data: response.data });
      setPage(response.data.page || requestedPage);
    } catch (error) {
      setDeviceState({
        loading: false,
        error: error.response?.data?.detail || error.message || 'Failed to load sensor devices.',
        data: null,
      });
    }
  }, [page, sensorStatus, zoneFilter]);

  const fetchUnsupportedIdentities = useCallback(async () => {
    setUnsupportedState((current) => ({ ...current, loading: true, error: null }));
    try {
      const response = await sensorDeviceAdminApi.listUnsupportedIdentities();
      setUnsupportedState({ loading: false, error: null, data: response.data });
    } catch (error) {
      setUnsupportedState({
        loading: false,
        error: error.response?.data?.detail || error.message || 'Failed to load unsupported sensor IDs.',
        data: null,
      });
    }
  }, []);

  const fetchBrokerProvisioning = useCallback(async (config = DEFAULT_PROVISIONING_CONFIG) => {
    setProvisioningState((current) => ({ ...current, loading: true, error: null }));
    try {
      const response = await sensorDeviceAdminApi.getBrokerProvisioning({
        passwordFilePath: config.passwordFilePath,
        dynamicSecurityRole: config.dynamicSecurityRole,
      });
      setProvisioningState({ loading: false, error: null, data: response.data });
    } catch (error) {
      setProvisioningState({
        loading: false,
        error: error.response?.data?.detail || error.message || 'Failed to generate broker provisioning artifacts.',
        data: null,
      });
    }
  }, []);

  const fetchBrokerProvisioningEvidence = useCallback(async () => {
    setProvisioningEvidenceState((current) => ({ ...current, loading: true, error: null }));
    try {
      const response = await sensorDeviceAdminApi.getBrokerProvisioningEvidence();
      setProvisioningEvidenceState({ loading: false, error: null, data: response.data });
    } catch (error) {
      setProvisioningEvidenceState({
        loading: false,
        error: error.response?.data?.detail || error.message || 'Failed to load broker provisioning evidence.',
        data: null,
      });
    }
  }, []);

  const fetchBrokerProvisioningEvidenceHistory = useCallback(async ({ brokerHost, nextPage } = {}) => {
    const requestedBrokerHost = brokerHost ?? evidenceHistoryFilter.brokerHost;
    const requestedPage = nextPage ?? evidenceHistoryPage;

    setProvisioningEvidenceHistoryState((current) => ({ ...current, loading: true, error: null }));
    try {
      const response = await sensorDeviceAdminApi.getBrokerProvisioningEvidenceHistory({
        brokerHost: requestedBrokerHost,
        page: requestedPage,
        pageSize: PROVISIONING_EVIDENCE_PAGE_SIZE,
      });
      setProvisioningEvidenceHistoryState({ loading: false, error: null, data: response.data });
      setEvidenceHistoryPage(response.data.page || requestedPage);
    } catch (error) {
      setProvisioningEvidenceHistoryState({
        loading: false,
        error: error.response?.data?.detail || error.message || 'Failed to load broker provisioning evidence history.',
        data: null,
      });
    }
  }, [evidenceHistoryFilter.brokerHost, evidenceHistoryPage]);

  const fetchRejections = useCallback(async ({ filter, nextPage } = {}) => {
    const requestedFilter = filter ?? rejectionFilter;
    const requestedPage = nextPage ?? rejectionPage;
    const windowHours = Number(requestedFilter.windowHours) || 24;

    setRejectionState((current) => ({ ...current, loading: true, error: null }));
    try {
      const response = await sensorDeviceAdminApi.listMqttRejections({
        windowHours,
        sensorId: requestedFilter.sensorId,
        reason: requestedFilter.reason === 'all' ? '' : requestedFilter.reason,
        page: requestedPage,
        pageSize: REJECTION_PAGE_SIZE,
      });
      setRejectionState({ loading: false, error: null, data: response.data });
      setRejectionPage(response.data.page || requestedPage);
    } catch (error) {
      setRejectionState({
        loading: false,
        error: error.response?.data?.detail || error.message || 'Failed to load MQTT rejection events.',
        data: null,
      });
    }
  }, [rejectionFilter, rejectionPage]);

  useEffect(() => {
    if (!hasSavedOperatorToken) return;
    // Initial and filter/page-driven registry load mirrors the existing operator QR flow.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchDevices();
  }, [fetchDevices, hasSavedOperatorToken]);

  useEffect(() => {
    if (!hasSavedOperatorToken) return;
    // Unsupported identity cleanup is intentionally separate from the paged registry list.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchUnsupportedIdentities();
  }, [fetchUnsupportedIdentities, hasSavedOperatorToken]);

  useEffect(() => {
    if (!hasSavedOperatorToken) return;
    // Broker provisioning output is generated from current registry state.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchBrokerProvisioning();
  }, [fetchBrokerProvisioning, hasSavedOperatorToken]);

  useEffect(() => {
    if (!hasSavedOperatorToken) return;
    // Last-applied evidence is stored as operator audit metadata.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchBrokerProvisioningEvidence();
  }, [fetchBrokerProvisioningEvidence, hasSavedOperatorToken]);

  useEffect(() => {
    if (!hasSavedOperatorToken) return;
    // Evidence history is paged separately from the latest evidence summary.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchBrokerProvisioningEvidenceHistory();
  }, [fetchBrokerProvisioningEvidenceHistory, hasSavedOperatorToken]);

  useEffect(() => {
    if (!hasSavedOperatorToken) return;
    // Initial and filter/page-driven audit load mirrors the registry list flow.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchRejections();
  }, [fetchRejections, hasSavedOperatorToken]);

  useEffect(() => {
    if (actionState.loading || (!actionState.error && !actionState.success)) return;
    actionStatusRef.current?.scrollIntoView({ block: 'start', behavior: 'auto' });
  }, [actionState.error, actionState.loading, actionState.success]);

  const handleFilterSubmit = useCallback((event) => {
    event.preventDefault();
    setSensorStatus(draftStatus);
    setZoneFilter(draftZone.trim());
    setPage(1);
  }, [draftStatus, draftZone]);

  const handleRejectionFilterSubmit = useCallback((event) => {
    event.preventDefault();
    const nextFilter = {
      windowHours: Math.max(1, Number(rejectionDraft.windowHours) || 24),
      sensorId: rejectionDraft.sensorId.trim(),
      reason: rejectionDraft.reason,
    };
    setRejectionFilter(nextFilter);
    setRejectionPage(1);
  }, [rejectionDraft]);

  const applyEvidenceHistoryFilter = useCallback((event) => {
    event.preventDefault();
    setEvidenceHistoryPage(1);
    setEvidenceHistoryFilter({ brokerHost: evidenceHistoryDraft.brokerHost });
  }, [evidenceHistoryDraft.brokerHost]);

  const clearEvidenceHistoryFilter = useCallback(() => {
    setEvidenceHistoryDraft({ brokerHost: '' });
    setEvidenceHistoryPage(1);
    setEvidenceHistoryFilter({ brokerHost: '' });
  }, []);

  const saveOperatorToken = useCallback(() => {
    setOperatorToken(operatorTokenInput);
    setHasSavedOperatorToken(Boolean(operatorTokenInput.trim()));
    setActionState({
      loading: false,
      error: null,
      success: operatorTokenInput.trim() ? 'Operator token saved for this browser.' : 'Operator token cleared.',
    });
  }, [operatorTokenInput]);

  const resetForm = useCallback(() => {
    setPendingSensorId(null);
    setFormState(EMPTY_FORM);
  }, []);

  const handleFormChange = useCallback((field, value) => {
    setFormState((current) => ({ ...current, [field]: value }));
  }, []);

  const handleSubmit = useCallback(async (event) => {
    event.preventDefault();
    const normalizedSensorId = formState.sensorId.trim();
    if (!normalizedSensorId) {
      setActionState({ loading: false, error: 'Enter a sensor ID before saving.', success: null });
      return;
    }
    if (!SENSOR_ID_PATTERN_RE.test(normalizedSensorId)) {
      setActionState({ loading: false, error: SENSOR_ID_PATTERN_MESSAGE, success: null });
      return;
    }

    setActionState({ loading: true, error: null, success: null });
    try {
      const response = await sensorDeviceAdminApi.upsert(normalizedSensorId, {
        label: formState.label,
        zone: formState.zone,
        ownerId: formState.ownerId,
        clearOwner: formState.clearOwner,
        expectedIntervalMinutes: formState.expectedIntervalMinutes,
        isActive: formState.isActive,
      });
      setActionState({
        loading: false,
        error: null,
        success: `Sensor ${response.data.sensor.sensor_id} saved.`,
      });
      setPendingSensorId(response.data.sensor.sensor_id);
      await Promise.all([
        fetchDevices(),
        fetchUnsupportedIdentities(),
        fetchBrokerProvisioning(provisioningDraft),
      ]);
    } catch (error) {
      setActionState({
        loading: false,
        error: error.response?.data?.detail || error.message || 'Sensor device save failed.',
        success: null,
      });
    }
  }, [fetchBrokerProvisioning, fetchDevices, fetchUnsupportedIdentities, formState, provisioningDraft]);

  const editSensor = useCallback((sensor) => {
    setPendingSensorId(sensor.sensor_id);
    setFormState({
      sensorId: sensor.sensor_id,
      label: sensor.label || '',
      zone: sensor.zone || '',
      ownerId: sensor.owner_id || '',
      clearOwner: false,
      expectedIntervalMinutes: sensor.expected_interval_minutes ? String(sensor.expected_interval_minutes) : '',
      isActive: sensor.is_active,
    });
  }, []);

  const updateSensorActiveState = useCallback(async (sensor) => {
    const isSafe = isBrokerSafeSensorId(sensor.sensor_id);
    if (!isSafe && !sensor.is_active) {
      setActionState({
        loading: false,
        error: 'Reissue a broker-safe sensor ID before reactivating this device.',
        success: null,
      });
      return;
    }

    setActionState({ loading: true, error: null, success: null });
    try {
      if (!isSafe && sensor.is_active) {
        const response = await sensorDeviceAdminApi.disableUnsupportedIdentities({ sensorIds: [sensor.sensor_id] });
        setActionState({
          loading: false,
          error: null,
          success: formatDisabledCount(response.data.disabled_count || 0),
        });
        await Promise.all([
          fetchDevices(),
          fetchUnsupportedIdentities(),
          fetchBrokerProvisioning(provisioningDraft),
        ]);
        return;
      }

      const response = sensor.is_active
        ? await sensorDeviceAdminApi.disable(sensor.sensor_id)
        : await sensorDeviceAdminApi.reactivate(sensor.sensor_id);
      setActionState({
        loading: false,
        error: null,
        success: `Sensor ${response.data.sensor.sensor_id} ${response.data.sensor.is_active ? 'reactivated' : 'disabled'}.`,
      });
      await Promise.all([
        fetchDevices(),
        fetchUnsupportedIdentities(),
        fetchBrokerProvisioning(provisioningDraft),
      ]);
    } catch (error) {
      setActionState({
        loading: false,
        error: error.response?.data?.detail || error.message || 'Sensor device action failed.',
        success: null,
      });
    }
  }, [fetchBrokerProvisioning, fetchDevices, fetchUnsupportedIdentities, provisioningDraft]);

  const cleanupUnsupportedIdentities = useCallback(async () => {
    setActionState({ loading: true, error: null, success: null });
    try {
      const response = await sensorDeviceAdminApi.disableUnsupportedIdentities();
      setActionState({
        loading: false,
        error: null,
        success: formatDisabledCount(response.data.disabled_count || 0),
      });
      await Promise.all([
        fetchDevices(),
        fetchUnsupportedIdentities(),
        fetchBrokerProvisioning(provisioningDraft),
      ]);
    } catch (error) {
      setActionState({
        loading: false,
        error: error.response?.data?.detail || error.message || 'Unsupported sensor ID cleanup failed.',
        success: null,
      });
    }
  }, [fetchBrokerProvisioning, fetchDevices, fetchUnsupportedIdentities, provisioningDraft]);

  const updateReissueDraft = useCallback((sensorId, value) => {
    setReissueDrafts((current) => ({
      ...current,
      [sensorId]: value,
    }));
  }, []);

  const reissueUnsupportedIdentity = useCallback(async (sensor) => {
    const newSensorId = String(reissueDrafts[sensor.sensor_id] || '').trim();
    if (!newSensorId) {
      setActionState({ loading: false, error: 'Enter a new broker-safe sensor ID before reissuing.', success: null });
      return;
    }
    if (!isBrokerSafeSensorId(newSensorId)) {
      setActionState({ loading: false, error: SENSOR_ID_PATTERN_MESSAGE, success: null });
      return;
    }

    setActionState({ loading: true, error: null, success: null });
    setReissuePendingId(sensor.sensor_id);
    try {
      const response = await sensorDeviceAdminApi.reissueUnsupportedIdentity({
        oldSensorId: sensor.sensor_id,
        newSensorId,
      });
      setReissueDrafts((current) => {
        const next = { ...current };
        delete next[sensor.sensor_id];
        return next;
      });
      setPendingSensorId(response.data.replacement_sensor.sensor_id);
      setActionState({
        loading: false,
        error: null,
        success: `Sensor ${sensor.sensor_id} reissued as ${response.data.replacement_sensor.sensor_id}. Rotate broker credentials.`,
      });
      await Promise.all([
        fetchDevices(),
        fetchUnsupportedIdentities(),
        fetchBrokerProvisioning(provisioningDraft),
      ]);
    } catch (error) {
      setActionState({
        loading: false,
        error: error.response?.data?.detail || error.message || 'Unsupported sensor ID reissue failed.',
        success: null,
      });
    } finally {
      setReissuePendingId(null);
    }
  }, [fetchBrokerProvisioning, fetchDevices, fetchUnsupportedIdentities, provisioningDraft, reissueDrafts]);

  const handleProvisioningSubmit = useCallback((event) => {
    event.preventDefault();
    fetchBrokerProvisioning(provisioningDraft);
  }, [fetchBrokerProvisioning, provisioningDraft]);

  const copyProvisioningText = useCallback(async (label, text) => {
    if (!text) {
      setActionState({ loading: false, error: `No ${label} artifact to copy.`, success: null });
      return;
    }
    if (!navigator.clipboard?.writeText) {
      setActionState({ loading: false, error: 'Clipboard access is not available in this browser context.', success: null });
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      setActionState({ loading: false, error: null, success: `${label} copied.` });
    } catch (error) {
      setActionState({
        loading: false,
        error: error.message || 'Clipboard write failed.',
        success: null,
      });
    }
  }, []);

  const downloadProvisioningBundle = useCallback(() => {
    const bundle = formatProvisioningBundle(provisioningState.data);
    if (!bundle) {
      setActionState({ loading: false, error: 'No broker provisioning bundle to download.', success: null });
      return;
    }
    downloadTextFile('agriguard-mqtt-broker-provisioning.txt', bundle);
    setActionState({ loading: false, error: null, success: 'Broker provisioning bundle downloaded.' });
  }, [provisioningState.data]);

  const recordProvisioningEvidence = useCallback(async (event) => {
    event.preventDefault();
    const bundle = formatProvisioningBundle(provisioningState.data);
    if (!provisioningState.data || !bundle) {
      setActionState({ loading: false, error: 'Generate broker provisioning artifacts before recording evidence.', success: null });
      return;
    }

    setActionState({ loading: true, error: null, success: null });
    try {
      const artifactHash = await sha256Hex(bundle);
      const response = await sensorDeviceAdminApi.recordBrokerProvisioningEvidence({
        mode: evidenceDraft.mode,
        artifactHash,
        artifactGeneratedAt: provisioningState.data.generated_at,
        appliedAt: new Date().toISOString(),
        brokerHost: evidenceDraft.brokerHost,
        runbookReference: evidenceDraft.runbookReference,
        activeSensorCount: provisioningState.data.active_sensor_count || 0,
        disabledSensorCount: provisioningState.data.disabled_sensor_count || 0,
        unsupportedSensorCount: provisioningState.data.unsupported_sensor_ids?.length || 0,
        credentialRotationRequired: !evidenceDraft.credentialsRotated,
        rotationNote: evidenceDraft.rotationNote,
      });
      setProvisioningEvidenceState({ loading: false, error: null, data: response.data });
      setActionState({ loading: false, error: null, success: 'Broker provisioning evidence recorded.' });
      await fetchBrokerProvisioningEvidenceHistory({ brokerHost: evidenceHistoryFilter.brokerHost, nextPage: 1 });
    } catch (error) {
      setActionState({
        loading: false,
        error: error.response?.data?.detail || error.message || 'Broker provisioning evidence record failed.',
        success: null,
      });
    }
  }, [evidenceDraft, evidenceHistoryFilter.brokerHost, fetchBrokerProvisioningEvidenceHistory, provisioningState.data]);

  const devices = deviceState.data?.items || [];
  const hasLoaded = Boolean(deviceState.data);
  const currentPage = deviceState.data?.page || page;
  const totalPages = deviceState.data?.total_pages || 1;
  const statRows = useMemo(() => [
    ['Total', deviceState.data?.total ?? 0],
    ['Active', deviceState.data?.active_count ?? 0],
    ['Disabled', deviceState.data?.disabled_count ?? 0],
  ], [deviceState.data]);
  const unsupportedItems = unsupportedState.data?.items || [];
  const unsupportedActiveCount = unsupportedState.data?.active_count || 0;
  const unsupportedTotal = unsupportedState.data?.total || 0;
  const provisioning = provisioningState.data;
  const latestProvisioningEvidence = provisioningEvidenceState.data?.latest || null;
  const provisioningEvidenceHistory = provisioningEvidenceHistoryState.data;
  const provisioningEvidenceHistoryItems = provisioningEvidenceHistory?.items || [];
  const passwordCommandText = useMemo(() => (
    commandLinesText([
      ...(provisioning?.password_file_commands || []),
      ...(provisioning?.password_file_delete_commands || []),
    ])
  ), [provisioning]);
  const dynamicSecurityText = useMemo(() => (
    commandLinesText(provisioning?.dynamic_security_commands || [])
  ), [provisioning]);

  return (
    <div className="mx-auto max-w-7xl space-y-5 px-4 py-5 text-foreground sm:space-y-8 sm:p-8">
      <div className="flex flex-col gap-3 sm:gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="mb-3 inline-flex items-center gap-2 rounded-md border border-sky-500/20 bg-sky-500/10 px-3 py-1 text-sm text-sky-300">
            <RadioTower className="h-4 w-4" />
            Operator Sensors
          </div>
          <h1 data-testid="sensor-device-heading" className="max-w-full text-2xl font-bold leading-tight text-foreground sm:text-3xl">Sensor Device Registry</h1>
        </div>

        <Card data-testid="sensor-operator-token-card" className="w-full border-primary/20 bg-primary/5 lg:w-[28rem]">
          <CardContent className="p-3 sm:p-4">
            <label htmlFor="sensor-operator-token" className="text-sm font-medium text-foreground">
              Operator bearer token
            </label>
            <div className="mt-2 grid grid-cols-[minmax(0,1fr)_5rem] gap-2">
              <Input
                id="sensor-operator-token"
                type="password"
                value={operatorTokenInput}
                onChange={(event) => setOperatorTokenInput(event.target.value)}
                placeholder="Paste Firebase/operator token"
                autoComplete="off"
                spellCheck={false}
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

      <Card data-testid="sensor-filter-panel">
        <CardContent className="p-4 sm:p-6">
          <form onSubmit={handleFilterSubmit} className="grid grid-cols-2 gap-3 lg:grid-cols-[12rem_minmax(0,1fr)_auto] lg:items-end">
            <div className="min-w-0">
              <label htmlFor="sensor-status" className="text-sm font-medium text-muted-foreground">
                Sensor state
              </label>
              <select
                id="sensor-status"
                value={draftStatus}
                onChange={(event) => setDraftStatus(event.target.value)}
                className="mt-2 flex min-h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:min-h-11"
              >
                {STATUS_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {formatStatusLabel(option)}
                  </option>
                ))}
              </select>
            </div>
            <div className="min-w-0">
              <label htmlFor="sensor-zone-filter" className="text-sm font-medium text-muted-foreground">
                Zone filter
              </label>
              <Input
                id="sensor-zone-filter"
                value={draftZone}
                onChange={(event) => setDraftZone(event.target.value)}
                placeholder="e.g. Packhouse"
                className="mt-2 min-h-10 sm:min-h-11"
              />
            </div>
            <Button type="submit" className="col-span-2 min-h-10 sm:min-h-11 lg:col-span-1" disabled={deviceState.loading}>
              {deviceState.loading ? <Loader2 className="animate-spin" /> : <Search />}
              Apply filters
            </Button>
          </form>
        </CardContent>
      </Card>

      <div ref={actionStatusRef} data-testid="sensor-action-status" aria-live="polite" role="status" className="scroll-mt-24 min-h-0 text-sm empty:hidden">
        {!hasSavedOperatorToken && (
          <span className="inline-flex items-center gap-2 text-amber-300">
            <AlertTriangle className="h-4 w-4" />
            {PROTECTED_AUTO_LOAD_MESSAGE}
          </span>
        )}
        {deviceState.loading && <span className="text-muted-foreground">Loading sensor registry...</span>}
        {unsupportedState.loading && <span className="text-muted-foreground">Loading unsupported sensor IDs...</span>}
        {provisioningState.loading && <span className="text-muted-foreground">Generating broker provisioning artifacts...</span>}
        {provisioningEvidenceState.loading && <span className="text-muted-foreground">Loading broker provisioning evidence...</span>}
        {deviceState.error && (
          <span className="inline-flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-4 w-4" />
            {deviceState.error}
          </span>
        )}
        {provisioningState.error && (
          <span className="inline-flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-4 w-4" />
            {provisioningState.error}
          </span>
        )}
        {provisioningEvidenceState.error && (
          <span className="inline-flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-4 w-4" />
            {provisioningEvidenceState.error}
          </span>
        )}
        {unsupportedState.error && (
          <span className="inline-flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-4 w-4" />
            {unsupportedState.error}
          </span>
        )}
        {actionState.error && (
          <span className="inline-flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-4 w-4" />
            {actionState.error}
          </span>
        )}
        {actionState.success && (
          <span className="inline-flex items-center gap-2 text-emerald-300">
            <CheckCircle2 className="h-4 w-4" />
            {actionState.success}
          </span>
        )}
        {rejectionState.loading && <span className="text-muted-foreground">Loading MQTT rejection events...</span>}
        {rejectionState.error && (
          <span className="inline-flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-4 w-4" />
            {rejectionState.error}
          </span>
        )}
      </div>

      {hasLoaded && (
        <div data-testid="sensor-stat-grid" className="grid grid-cols-3 gap-2 sm:gap-3">
          {statRows.map(([label, value]) => (
            <SensorStat key={label} label={label} value={value} />
          ))}
        </div>
      )}

      <Card className="border-amber-500/30 bg-amber-500/[0.04]">
        <CardHeader className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-lg">
              <ShieldAlert className="h-5 w-5 text-amber-300" />
              Unsupported broker identities
            </CardTitle>
            <p className="mt-2 text-sm text-muted-foreground">
              {unsupportedState.data
                ? `${unsupportedActiveCount} active / ${unsupportedTotal} total unsupported sensor IDs`
                : 'Broker provisioning cleanup queue'}
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Button
              type="button"
              variant="outline"
              onClick={fetchUnsupportedIdentities}
              disabled={unsupportedState.loading}
              className="min-h-11"
            >
              {unsupportedState.loading ? <Loader2 className="animate-spin" /> : <RefreshCw />}
              Refresh IDs
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={cleanupUnsupportedIdentities}
              disabled={actionState.loading || unsupportedActiveCount === 0}
              className="min-h-11"
            >
              <Power />
              Disable active unsupported IDs
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {unsupportedState.data && unsupportedItems.length === 0 && (
            <div className="rounded-lg border border-dashed border-border p-8 text-center">
              <CheckCircle2 className="mx-auto h-9 w-9 text-emerald-300" />
              <h2 className="mt-3 text-lg font-semibold">No unsupported broker identities</h2>
            </div>
          )}

          {unsupportedItems.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[680px] border-collapse text-left text-sm">
                <thead className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th scope="col" className="py-3 pr-4">Sensor</th>
                    <th scope="col" className="py-3 pr-4">State</th>
                    <th scope="col" className="py-3 pr-4">Zone</th>
                    <th scope="col" className="py-3 pr-4">Last seen</th>
                    <th scope="col" className="py-3">Next action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {unsupportedItems.map((sensor, index) => {
                    const reissueInputId = `reissue-sensor-id-${index}`;
                    const isReissuing = actionState.loading && reissuePendingId === sensor.sensor_id;
                    return (
                      <tr key={sensor.sensor_id} className="align-top">
                        <td className="py-4 pr-4">
                          <div className="font-mono text-foreground">{sensor.sensor_id}</div>
                          <div className="mt-1 max-w-56 truncate text-xs text-muted-foreground">{sensor.label || 'Unlabeled'}</div>
                        </td>
                        <td className="py-4 pr-4">
                          <SensorStateBadge isActive={sensor.is_active} />
                        </td>
                        <td className="py-4 pr-4 text-muted-foreground">{sensor.zone || 'Unassigned'}</td>
                        <td className="py-4 pr-4 text-muted-foreground">{formatDateTime(sensor.last_seen_at)}</td>
                        <td className="py-4">
                          <div className="min-w-64 space-y-2">
                            <p className="text-xs text-muted-foreground">
                              {sensor.is_active ? 'Old ID will be disabled; rotate broker credentials after reissue.' : 'Create replacement ID before reactivation.'}
                            </p>
                            <div className="flex flex-col gap-2 sm:flex-row">
                              <label className="sr-only" htmlFor={reissueInputId}>
                                New broker-safe ID for {sensor.sensor_id}
                              </label>
                              <Input
                                id={reissueInputId}
                                value={reissueDrafts[sensor.sensor_id] || ''}
                                onChange={(event) => updateReissueDraft(sensor.sensor_id, event.target.value)}
                                placeholder="e.g. dock-c-probe-01"
                                pattern={SENSOR_ID_PATTERN}
                                className="min-h-10 min-w-0 font-mono"
                              />
                              <Button
                                type="button"
                                variant="secondary"
                                onClick={() => reissueUnsupportedIdentity(sensor)}
                                disabled={actionState.loading}
                                className="min-h-10 shrink-0"
                              >
                                {isReissuing ? <Loader2 className="animate-spin" /> : <KeyRound />}
                                Reissue ID
                              </Button>
                            </div>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="border-sky-500/20 bg-sky-500/[0.04]">
        <CardHeader className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Terminal className="h-5 w-5 text-sky-300" />
              MQTT broker provisioning
            </CardTitle>
            <p className="mt-2 text-sm text-muted-foreground">
              {provisioning
                ? `${provisioning.active_sensor_count} active / ${provisioning.disabled_sensor_count} disabled broker-safe sensors`
                : 'ACL, password-file, and dynamic-security artifacts'}
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Button
              type="button"
              variant="outline"
              onClick={() => fetchBrokerProvisioning(provisioningDraft)}
              disabled={provisioningState.loading}
              className="min-h-11"
            >
              {provisioningState.loading ? <Loader2 className="animate-spin" /> : <RefreshCw />}
              Refresh artifacts
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={downloadProvisioningBundle}
              disabled={!provisioning || provisioningState.loading}
              className="min-h-11"
            >
              <Download />
              Download bundle
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          <form onSubmit={handleProvisioningSubmit} className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_18rem_auto] lg:items-end">
            <div>
              <label htmlFor="provisioning-password-file" className="text-sm font-medium text-muted-foreground">
                Password file path
              </label>
              <Input
                id="provisioning-password-file"
                value={provisioningDraft.passwordFilePath}
                onChange={(event) => setProvisioningDraft((current) => ({ ...current, passwordFilePath: event.target.value }))}
                autoComplete="off"
                spellCheck={false}
                className="mt-2 min-h-11 font-mono"
              />
            </div>
            <div>
              <label htmlFor="provisioning-dynsec-role" className="text-sm font-medium text-muted-foreground">
                Dynamic role
              </label>
              <Input
                id="provisioning-dynsec-role"
                value={provisioningDraft.dynamicSecurityRole}
                onChange={(event) => setProvisioningDraft((current) => ({ ...current, dynamicSecurityRole: event.target.value }))}
                className="mt-2 min-h-11 font-mono"
              />
            </div>
            <Button type="submit" className="min-h-11" disabled={provisioningState.loading}>
              {provisioningState.loading ? <Loader2 className="animate-spin" /> : <FileText />}
              Generate
            </Button>
          </form>

          <div className="rounded-lg border border-border bg-black/10 p-4">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
              <div>
                <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                  <History className="h-4 w-4 text-sky-300" />
                  Last applied evidence
                </div>
                {latestProvisioningEvidence ? (
                  <div className="mt-3 grid gap-2 text-sm text-muted-foreground sm:grid-cols-2 xl:grid-cols-4">
                    <span>
                      Applied <strong className="font-medium text-foreground">{formatDateTime(latestProvisioningEvidence.applied_at)}</strong>
                    </span>
                    <span>
                      Mode <strong className="font-medium text-foreground">{formatReasonLabel(latestProvisioningEvidence.mode)}</strong>
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                      <Fingerprint className="h-3.5 w-3.5" />
                      <strong className="font-mono font-medium text-foreground">
                        {latestProvisioningEvidence.artifact_hash.slice(0, 12)}
                      </strong>
                    </span>
                    <span>
                      {latestProvisioningEvidence.active_sensor_count} active / {latestProvisioningEvidence.disabled_sensor_count} disabled
                    </span>
                    <span>
                      Broker <strong className="font-medium text-foreground">{latestProvisioningEvidence.broker_host || 'Not recorded'}</strong>
                    </span>
                    <span>
                      Runbook <strong className="font-medium text-foreground">{latestProvisioningEvidence.runbook_reference || 'Not recorded'}</strong>
                    </span>
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-muted-foreground">No broker application evidence recorded.</p>
                )}
                <Badge
                  variant={!latestProvisioningEvidence || latestProvisioningEvidence.credential_rotation_required ? 'warning' : 'success'}
                  className="mt-3"
                >
                  {!latestProvisioningEvidence || latestProvisioningEvidence.credential_rotation_required ? (
                    <AlertTriangle className="h-3.5 w-3.5" />
                  ) : (
                    <ShieldCheck className="h-3.5 w-3.5" />
                  )}
                  {!latestProvisioningEvidence
                    ? 'No evidence recorded'
                    : latestProvisioningEvidence.credential_rotation_required
                      ? 'Credential rotation required'
                      : 'Credential rotation recorded'}
                </Badge>
              </div>

              <form onSubmit={recordProvisioningEvidence} className="grid w-full gap-3 xl:max-w-xl">
                <div className="grid gap-3 sm:grid-cols-[12rem_minmax(0,1fr)]">
                  <div>
                    <label htmlFor="provisioning-evidence-mode" className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Evidence mode
                    </label>
                    <select
                      id="provisioning-evidence-mode"
                      value={evidenceDraft.mode}
                      onChange={(event) => setEvidenceDraft((current) => ({ ...current, mode: event.target.value }))}
                      className="mt-2 flex min-h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <option value="combined">Combined</option>
                      <option value="password_file">Password file</option>
                      <option value="dynamic_security">Dynamic security</option>
                    </select>
                  </div>
                  <div>
                    <label htmlFor="provisioning-evidence-broker" className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Broker host
                    </label>
                    <Input
                      id="provisioning-evidence-broker"
                      value={evidenceDraft.brokerHost}
                      onChange={(event) => setEvidenceDraft((current) => ({ ...current, brokerHost: event.target.value }))}
                      placeholder="e.g. mosquitto-prod-01"
                      className="mt-2 min-h-10"
                    />
                  </div>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <label htmlFor="provisioning-evidence-runbook" className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Runbook or change reference
                    </label>
                    <Input
                      id="provisioning-evidence-runbook"
                      value={evidenceDraft.runbookReference}
                      onChange={(event) => setEvidenceDraft((current) => ({ ...current, runbookReference: event.target.value }))}
                      placeholder="e.g. CHG-2026-0610"
                      className="mt-2 min-h-10"
                    />
                  </div>
                  <div>
                    <label htmlFor="provisioning-evidence-note" className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Evidence note, no secrets
                    </label>
                    <Input
                      id="provisioning-evidence-note"
                      value={evidenceDraft.rotationNote}
                      onChange={(event) => setEvidenceDraft((current) => ({ ...current, rotationNote: event.target.value }))}
                      placeholder="e.g. Applied by ops runbook, passwords rotated in broker"
                      autoComplete="off"
                      spellCheck={false}
                      className="mt-2 min-h-10"
                    />
                  </div>
                </div>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <label className="flex min-h-10 items-center gap-3 rounded-md border border-border px-3 py-2 text-sm text-foreground">
                    <input
                      type="checkbox"
                      checked={evidenceDraft.credentialsRotated}
                      onChange={(event) => setEvidenceDraft((current) => ({ ...current, credentialsRotated: event.target.checked }))}
                      className="h-4 w-4 rounded border-input"
                    />
                    Credentials rotated
                  </label>
                  <Button type="submit" disabled={!provisioning || actionState.loading} className="min-h-10">
                    {actionState.loading ? <Loader2 className="animate-spin" /> : <ShieldCheck />}
                    Record applied evidence
                  </Button>
                </div>
              </form>
            </div>

            <div className="mt-5 border-t border-border pt-5">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
                <div>
                  <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                    <Clock className="h-4 w-4 text-sky-300" />
                    Evidence history
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {provisioningEvidenceHistory
                      ? `${provisioningEvidenceHistory.total} recorded broker application events`
                      : 'Recent broker application events'}
                  </p>
                </div>
                <form onSubmit={applyEvidenceHistoryFilter} className="flex flex-col gap-2 sm:flex-row sm:items-end">
                  <div>
                    <label htmlFor="provisioning-evidence-history-broker" className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Broker host filter
                    </label>
                    <Input
                      id="provisioning-evidence-history-broker"
                      value={evidenceHistoryDraft.brokerHost}
                      onChange={(event) => setEvidenceHistoryDraft({ brokerHost: event.target.value })}
                      placeholder="e.g. mosquitto-prod-01"
                      className="mt-2 min-h-10 min-w-64"
                    />
                  </div>
                  <Button type="submit" variant="secondary" className="min-h-10" disabled={provisioningEvidenceHistoryState.loading}>
                    {provisioningEvidenceHistoryState.loading ? <Loader2 className="animate-spin" /> : <Search />}
                    Filter history
                  </Button>
                  <Button type="button" variant="outline" className="min-h-10" onClick={clearEvidenceHistoryFilter} disabled={provisioningEvidenceHistoryState.loading}>
                    <RefreshCw />
                    Clear
                  </Button>
                </form>
              </div>

              {provisioningEvidenceHistoryState.error && (
                <div className="mt-4 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                  {provisioningEvidenceHistoryState.error}
                </div>
              )}

              {provisioningEvidenceHistoryItems.length > 0 ? (
                <div className="mt-4 overflow-x-auto">
                  <table className="w-full min-w-[760px] border-collapse text-left text-xs">
                    <thead className="border-b border-border uppercase tracking-wide text-muted-foreground">
                      <tr>
                        <th scope="col" className="py-2 pr-4">Applied</th>
                        <th scope="col" className="py-2 pr-4">Broker</th>
                        <th scope="col" className="py-2 pr-4">Runbook</th>
                        <th scope="col" className="py-2 pr-4">Mode</th>
                        <th scope="col" className="py-2 pr-4">Hash</th>
                        <th scope="col" className="py-2">Rotation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border text-muted-foreground">
                      {provisioningEvidenceHistoryItems.map((item) => (
                        <tr key={item.id} className="align-top">
                          <td className="py-3 pr-4 text-foreground">{formatDateTime(item.applied_at)}</td>
                          <td className="py-3 pr-4">{item.broker_host || 'Not recorded'}</td>
                          <td className="py-3 pr-4">{item.runbook_reference || 'Not recorded'}</td>
                          <td className="py-3 pr-4">{formatReasonLabel(item.mode)}</td>
                          <td className="py-3 pr-4 font-mono text-foreground">{item.artifact_hash.slice(0, 12)}</td>
                          <td className="py-3">{item.credential_rotation_required ? 'Required' : 'Recorded'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="mt-4 rounded-md border border-dashed border-border p-4 text-sm text-muted-foreground">
                  No broker provisioning evidence history found.
                </p>
              )}

              {provisioningEvidenceHistory && provisioningEvidenceHistory.total_pages > 1 && (
                <div className="mt-4 flex flex-col gap-3 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
                  <span>
                    Page {provisioningEvidenceHistory.page} / {provisioningEvidenceHistory.total_pages}
                  </span>
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setEvidenceHistoryPage((value) => Math.max(1, value - 1))}
                      disabled={provisioningEvidenceHistory.page === 1 || provisioningEvidenceHistoryState.loading}
                    >
                      Previous
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setEvidenceHistoryPage((value) => Math.min(provisioningEvidenceHistory.total_pages, value + 1))}
                      disabled={provisioningEvidenceHistory.page === provisioningEvidenceHistory.total_pages || provisioningEvidenceHistoryState.loading}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </div>

          {provisioning && (
            <>
              {provisioning.unsupported_sensor_ids.length > 0 && (
                <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-100">
                  <div className="flex items-center gap-2 font-medium">
                    <ShieldAlert className="h-4 w-4" />
                    {provisioning.unsupported_sensor_ids.length} unsupported sensor IDs omitted
                  </div>
                  <p className="mt-2 font-mono text-xs text-amber-50/90">
                    {provisioning.unsupported_sensor_ids.join(', ')}
                  </p>
                </div>
              )}

              <div className="grid gap-4 xl:grid-cols-3">
                <section className="rounded-lg border border-border bg-black/20">
                  <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
                    <div>
                      <h2 className="text-sm font-semibold text-foreground">ACL file</h2>
                      <p className="mt-1 text-xs text-muted-foreground">`mosquitto_acl_file` content</p>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => copyProvisioningText('ACL file', provisioning.acl_file)}
                    >
                      <Copy />
                      Copy
                    </Button>
                  </div>
                  <pre className="max-h-72 overflow-auto p-4 text-xs leading-relaxed text-slate-100"><code>{provisioning.acl_file}</code></pre>
                </section>

                <section className="rounded-lg border border-border bg-black/20">
                  <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
                    <div>
                      <h2 className="text-sm font-semibold text-foreground">Password file commands</h2>
                      <p className="mt-1 text-xs text-muted-foreground">Interactive `mosquitto_passwd` calls</p>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => copyProvisioningText('Password commands', passwordCommandText)}
                    >
                      <KeyRound />
                      Copy
                    </Button>
                  </div>
                  <pre className="max-h-72 overflow-auto p-4 text-xs leading-relaxed text-slate-100"><code>{passwordCommandText}</code></pre>
                </section>

                <section className="rounded-lg border border-border bg-black/20">
                  <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
                    <div>
                      <h2 className="text-sm font-semibold text-foreground">Dynamic security</h2>
                      <p className="mt-1 text-xs text-muted-foreground">`mosquitto_ctrl dynsec` commands</p>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => copyProvisioningText('Dynamic security commands', dynamicSecurityText)}
                    >
                      <Copy />
                      Copy
                    </Button>
                  </div>
                  <pre className="max-h-72 overflow-auto p-4 text-xs leading-relaxed text-slate-100"><code>{dynamicSecurityText}</code></pre>
                </section>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[24rem_minmax(0,1fr)]">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">{pendingSensorId ? 'Edit sensor' : 'Register sensor'}</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} noValidate className="space-y-4">
              <div>
                <label htmlFor="sensor-id" className="text-sm font-medium text-muted-foreground">
                  Sensor ID
                </label>
                <Input
                  id="sensor-id"
                  value={formState.sensorId}
                  onChange={(event) => handleFormChange('sensorId', event.target.value)}
                  placeholder="e.g. packhouse-probe-01"
                  className="mt-2 min-h-11 font-mono"
                  disabled={Boolean(pendingSensorId)}
                  pattern={SENSOR_ID_PATTERN}
                  title={SENSOR_ID_PATTERN_MESSAGE}
                  aria-describedby="sensor-id-hint"
                />
                <p id="sensor-id-hint" className="mt-2 text-xs text-muted-foreground">
                  Letters, numbers, dot, underscore, colon, and hyphen.
                </p>
              </div>
              <div>
                <label htmlFor="sensor-label" className="text-sm font-medium text-muted-foreground">
                  Label
                </label>
                <Input
                  id="sensor-label"
                  value={formState.label}
                  onChange={(event) => handleFormChange('label', event.target.value)}
                  placeholder="Packhouse probe 01"
                  className="mt-2 min-h-11"
                />
              </div>
              <div>
                <label htmlFor="sensor-zone" className="text-sm font-medium text-muted-foreground">
                  Assigned zone
                </label>
                <Input
                  id="sensor-zone"
                  value={formState.zone}
                  onChange={(event) => handleFormChange('zone', event.target.value)}
                  placeholder="Packhouse"
                  className="mt-2 min-h-11"
                />
              </div>
              <div>
                <label htmlFor="sensor-owner" className="text-sm font-medium text-muted-foreground">
                  Owner ID
                </label>
                <Input
                  id="sensor-owner"
                  value={formState.ownerId}
                  onChange={(event) => {
                    handleFormChange('ownerId', event.target.value);
                    if (event.target.value.trim()) {
                      handleFormChange('clearOwner', false);
                    }
                  }}
                  placeholder="tenant or operator key"
                  className="mt-2 min-h-11 font-mono"
                  aria-describedby="sensor-owner-hint"
                  disabled={formState.clearOwner}
                />
                <p id="sensor-owner-hint" className="mt-2 text-xs text-muted-foreground">
                  Optional tenant owner key.
                </p>
              </div>
              <label className="flex min-h-11 items-start gap-3 rounded-md border border-border px-3 py-2 text-sm text-foreground">
                <input
                  type="checkbox"
                  checked={formState.clearOwner}
                  onChange={(event) => {
                    handleFormChange('clearOwner', event.target.checked);
                    if (event.target.checked) {
                      handleFormChange('ownerId', '');
                    }
                  }}
                  className="mt-0.5 h-4 w-4 rounded border-input"
                />
                <span>
                  Clear owner
                  <span className="mt-1 block text-xs text-muted-foreground">
                    Global operators only; delegated operators keep their assigned owner scope.
                  </span>
                </span>
              </label>
              <div>
                <label htmlFor="sensor-interval" className="text-sm font-medium text-muted-foreground">
                  Expected interval minutes
                </label>
                <Input
                  id="sensor-interval"
                  type="number"
                  min="1"
                  max="1440"
                  value={formState.expectedIntervalMinutes}
                  onChange={(event) => handleFormChange('expectedIntervalMinutes', event.target.value)}
                  className="mt-2 min-h-11"
                />
              </div>
              <label className="flex min-h-11 items-center gap-3 rounded-md border border-border px-3 py-2 text-sm text-foreground">
                <input
                  type="checkbox"
                  checked={formState.isActive}
                  onChange={(event) => handleFormChange('isActive', event.target.checked)}
                  className="h-4 w-4 rounded border-input"
                />
                Active
              </label>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Button type="submit" className="min-h-11" disabled={actionState.loading}>
                  {actionState.loading ? <Loader2 className="animate-spin" /> : pendingSensorId ? <Save /> : <Plus />}
                  {pendingSensorId ? 'Save sensor' : 'Register sensor'}
                </Button>
                <Button type="button" variant="outline" onClick={resetForm} className="min-h-11">
                  Reset
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <CardTitle className="text-lg">Registered sensors</CardTitle>
            <Button type="button" variant="outline" onClick={() => fetchDevices()} disabled={deviceState.loading} className="min-h-11">
              {deviceState.loading ? <Loader2 className="animate-spin" /> : <RefreshCw />}
              Refresh
            </Button>
          </CardHeader>
          <CardContent>
            {!hasLoaded && !deviceState.loading && (
              <div className="rounded-lg border border-dashed border-border p-10 text-center">
                <RadioTower className="mx-auto h-10 w-10 text-muted-foreground" />
                <h2 className="mt-4 text-lg font-semibold">No registry data loaded</h2>
              </div>
            )}

            {hasLoaded && devices.length === 0 && (
              <div className="rounded-lg border border-dashed border-border p-10 text-center">
                <AlertTriangle className="mx-auto h-10 w-10 text-amber-300" />
                <h2 className="mt-4 text-lg font-semibold">No sensors match this filter</h2>
              </div>
            )}

            {devices.length > 0 && (
              <div className="overflow-visible md:overflow-x-auto">
                <table
                  data-testid="registered-sensors-table"
                  className="w-full border-separate border-spacing-0 text-left text-sm md:min-w-[940px] md:border-collapse"
                >
                  <thead className="hidden border-b border-border text-xs uppercase tracking-wide text-muted-foreground md:table-header-group">
                    <tr>
                      <th scope="col" className="py-3 pr-4">Sensor</th>
                      <th scope="col" className="py-3 pr-4">State</th>
                      <th scope="col" className="py-3 pr-4">Owner</th>
                      <th scope="col" className="py-3 pr-4">Zone</th>
                      <th scope="col" className="py-3 pr-4">Interval</th>
                      <th scope="col" className="py-3 pr-4">Last seen</th>
                      <th scope="col" className="py-3 pr-4">Battery</th>
                      <th scope="col" className="py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="block space-y-3 md:table-row-group md:divide-y md:divide-border md:space-y-0">
                    {devices.map((sensor) => {
                      const isSafe = isBrokerSafeSensorId(sensor.sensor_id);
                      const canToggle = isSafe || sensor.is_active;
                      return (
                        <tr
                          key={sensor.sensor_id}
                          data-testid="registered-sensor-row"
                          className="block rounded-lg border border-border bg-background/40 p-4 align-top md:table-row md:border-0 md:bg-transparent md:p-0"
                        >
                          <td className="block border-b border-border/60 pb-3 md:table-cell md:border-0 md:py-4 md:pr-4">
                            <span className="mb-2 block text-xs font-semibold uppercase tracking-wide text-muted-foreground md:hidden">
                              Sensor
                            </span>
                            <div className="break-all font-mono text-foreground">{sensor.sensor_id}</div>
                            <div className="mt-1 max-w-56 truncate text-xs text-muted-foreground">{sensor.label || 'Unlabeled'}</div>
                            {!isSafe && (
                              <Badge variant="warning" className="mt-2">
                                <ShieldAlert className="h-3.5 w-3.5" />
                                Broker unsafe
                              </Badge>
                            )}
                          </td>
                          <td className="flex items-center justify-between gap-3 border-b border-border/60 py-3 md:table-cell md:border-0 md:py-4 md:pr-4">
                            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground md:hidden">
                              State
                            </span>
                            <SensorStateBadge isActive={sensor.is_active} />
                          </td>
                          <td className="flex items-center justify-between gap-3 border-b border-border/60 py-3 md:table-cell md:border-0 md:py-4 md:pr-4">
                            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground md:hidden">
                              Owner
                            </span>
                            <span className="max-w-[12rem] break-all text-right font-mono text-xs text-muted-foreground md:max-w-none md:text-left">
                              {sensor.owner_id || 'Unowned'}
                            </span>
                          </td>
                          <td className="flex items-center justify-between gap-3 border-b border-border/60 py-3 md:table-cell md:border-0 md:py-4 md:pr-4">
                            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground md:hidden">
                              Zone
                            </span>
                            <span className="inline-flex min-w-0 items-center gap-1.5 text-right text-muted-foreground md:text-left">
                              <MapPin className="h-3.5 w-3.5 flex-none" />
                              <span className="break-words">{sensor.zone || 'Unassigned'}</span>
                            </span>
                          </td>
                          <td className="flex items-center justify-between gap-3 border-b border-border/60 py-3 text-muted-foreground md:table-cell md:border-0 md:py-4 md:pr-4">
                            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground md:hidden">
                              Interval
                            </span>
                            <span>{sensor.expected_interval_minutes ? `${sensor.expected_interval_minutes} min` : 'Not set'}</span>
                          </td>
                          <td className="flex items-center justify-between gap-3 border-b border-border/60 py-3 text-muted-foreground md:table-cell md:border-0 md:py-4 md:pr-4">
                            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground md:hidden">
                              Last seen
                            </span>
                            <span className="text-right md:text-left">{formatDateTime(sensor.last_seen_at)}</span>
                          </td>
                          <td className="flex items-center justify-between gap-3 border-b border-border/60 py-3 md:table-cell md:border-0 md:py-4 md:pr-4">
                            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground md:hidden">
                              Battery
                            </span>
                            <span className="inline-flex items-center gap-1.5 text-muted-foreground">
                              <Battery className="h-3.5 w-3.5 flex-none" />
                              <span>{formatBattery(sensor.last_battery)}</span>
                            </span>
                          </td>
                          <td className="block pt-4 md:table-cell md:py-4 md:text-right">
                            <span className="mb-2 block text-xs font-semibold uppercase tracking-wide text-muted-foreground md:hidden">
                              Actions
                            </span>
                            <div className="flex flex-col gap-2 sm:flex-row md:justify-end">
                              <Button type="button" variant="outline" size="sm" onClick={() => editSensor(sensor)} className="min-h-10 w-full justify-center md:w-auto">
                                <Pencil />
                                Edit
                              </Button>
                              <Button
                                type="button"
                                variant={sensor.is_active ? 'destructive' : 'secondary'}
                                size="sm"
                                onClick={() => updateSensorActiveState(sensor)}
                                disabled={actionState.loading || !canToggle}
                                className={cn('min-h-10 w-full justify-center md:w-auto', actionState.loading && 'opacity-60')}
                                title={!canToggle ? 'Reissue a broker-safe sensor ID before reactivation.' : undefined}
                              >
                                <Power />
                                {sensor.is_active ? 'Disable' : isSafe ? 'Reactivate' : 'Reissue required'}
                              </Button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {hasLoaded && (
              <div className="mt-5 flex flex-col gap-3 border-t border-border pt-4 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
                <span aria-live="polite">Showing {devices.length} of {deviceState.data.total} matching sensors</span>
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

      <Card>
        <CardHeader className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <CardTitle className="text-lg">MQTT rejection audit</CardTitle>
            <p className="mt-2 text-sm text-muted-foreground">
              {rejectionState.data
                ? `${rejectionState.data.total} rejected attempts in the last ${rejectionState.data.window_hours} hours`
                : 'Rejected attempts from unregistered or disabled sensors'}
            </p>
          </div>
          <Button type="button" variant="outline" onClick={() => fetchRejections()} disabled={rejectionState.loading} className="min-h-11">
            {rejectionState.loading ? <Loader2 className="animate-spin" /> : <RefreshCw />}
            Refresh audit
          </Button>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleRejectionFilterSubmit} className="grid gap-4 lg:grid-cols-[10rem_minmax(0,1fr)_14rem_auto] lg:items-end">
            <div>
              <label htmlFor="mqtt-window-hours" className="text-sm font-medium text-muted-foreground">
                Window hours
              </label>
              <Input
                id="mqtt-window-hours"
                type="number"
                min="1"
                max="168"
                value={rejectionDraft.windowHours}
                onChange={(event) => setRejectionDraft((current) => ({ ...current, windowHours: event.target.value }))}
                className="mt-2 min-h-11"
              />
            </div>
            <div>
              <label htmlFor="mqtt-sensor-filter" className="text-sm font-medium text-muted-foreground">
                Audit sensor ID
              </label>
              <Input
                id="mqtt-sensor-filter"
                value={rejectionDraft.sensorId}
                onChange={(event) => setRejectionDraft((current) => ({ ...current, sensorId: event.target.value }))}
                placeholder="e.g. packhouse-probe-01"
                className="mt-2 min-h-11 font-mono"
              />
            </div>
            <div>
              <label htmlFor="mqtt-reason-filter" className="text-sm font-medium text-muted-foreground">
                Reason
              </label>
              <select
                id="mqtt-reason-filter"
                value={rejectionDraft.reason}
                onChange={(event) => setRejectionDraft((current) => ({ ...current, reason: event.target.value }))}
                className="mt-2 flex min-h-11 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {REJECTION_REASON_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {formatReasonLabel(option)}
                  </option>
                ))}
              </select>
            </div>
            <Button type="submit" className="min-h-11" disabled={rejectionState.loading}>
              {rejectionState.loading ? <Loader2 className="animate-spin" /> : <Search />}
              Filter audit
            </Button>
          </form>

          {rejectionState.data && Object.keys(rejectionState.data.reason_counts || {}).length > 0 && (
            <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
              {Object.entries(rejectionState.data.reason_counts).map(([reason, count]) => (
                <SensorStat key={reason} label={formatReasonLabel(reason)} value={count} />
              ))}
            </div>
          )}

          {rejectionState.data && rejectionState.data.items.length === 0 && (
            <div className="mt-5 rounded-lg border border-dashed border-border p-8 text-center">
              <CheckCircle2 className="mx-auto h-9 w-9 text-emerald-300" />
              <h2 className="mt-3 text-lg font-semibold">No rejected MQTT attempts</h2>
            </div>
          )}

          {rejectionState.data?.items.length > 0 && (
            <div className="mt-5 overflow-x-auto">
              <table className="w-full min-w-[760px] border-collapse text-left text-sm">
                <thead className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th scope="col" className="py-3 pr-4">Sensor</th>
                    <th scope="col" className="py-3 pr-4">Reason</th>
                    <th scope="col" className="py-3 pr-4">Occurred</th>
                    <th scope="col" className="py-3 pr-4">Registry gate</th>
                    <th scope="col" className="py-3">Message</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {rejectionState.data.items.map((event) => (
                    <tr key={event.id} className="align-top">
                      <td className="py-4 pr-4 font-mono text-foreground">{event.sensor_id || 'unknown'}</td>
                      <td className="py-4 pr-4">
                        <Badge variant="warning" className="capitalize">
                          <AlertTriangle className="h-3.5 w-3.5" />
                          {formatReasonLabel(event.reason)}
                        </Badge>
                      </td>
                      <td className="py-4 pr-4 text-muted-foreground">
                        <span className="inline-flex items-center gap-1.5">
                          <Clock className="h-3.5 w-3.5" />
                          {formatDateTime(event.occurred_at)}
                        </span>
                      </td>
                      <td className="py-4 pr-4">
                        <RegistryGateBadge isRequired={Boolean(event.registry_required)} />
                      </td>
                      <td className="py-4 text-muted-foreground">{event.error_message || 'No message'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {rejectionState.data && (
            <div className="mt-5 flex flex-col gap-3 border-t border-border pt-4 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
              <span aria-live="polite">Showing {rejectionState.data.items.length} of {rejectionState.data.total} rejected attempts</span>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setRejectionPage((value) => Math.max(1, value - 1))}
                  disabled={rejectionState.data.page === 1}
                >
                  Previous
                </Button>
                <span className="min-w-20 text-center">Page {rejectionState.data.page} / {rejectionState.data.total_pages}</span>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setRejectionPage((value) => Math.min(rejectionState.data.total_pages, value + 1))}
                  disabled={rejectionState.data.page === rejectionState.data.total_pages}
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
