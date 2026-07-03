import axios from 'axios';

export function resolveApiBaseUrl() {
  return import.meta.env.VITE_API_URL?.trim() || '/api';
}

const API_URL = resolveApiBaseUrl();

const api = axios.create({
  baseURL: API_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

export function getOperatorToken() {
  const envToken = import.meta.env.VITE_AGRIGUARD_OPERATOR_TOKEN;
  if (envToken) {
    return envToken;
  }
  if (typeof window === 'undefined') {
    return '';
  }
  return window.localStorage.getItem('agriguard-operator-token') || '';
}

export function hasOperatorToken() {
  return Boolean(getOperatorToken());
}

export function setOperatorToken(token) {
  if (typeof window === 'undefined') {
    return;
  }
  const normalizedToken = token.trim();
  if (normalizedToken) {
    window.localStorage.setItem('agriguard-operator-token', normalizedToken);
    return;
  }
  window.localStorage.removeItem('agriguard-operator-token');
}

export function withOperatorAuth(config = {}) {
  const token = getOperatorToken();
  if (!token) {
    return config;
  }
  return {
    ...config,
    headers: {
      ...config.headers,
      Authorization: `Bearer ${token}`,
    },
  };
}

function toProductPageResponse(response, { page, pageSize, search }) {
  const normalizedSearch = search.trim().toLowerCase();
  const allProducts = Array.isArray(response.data) ? response.data : [];
  const filteredProducts = normalizedSearch
    ? allProducts.filter(
        (product) =>
          product.id.toLowerCase().includes(normalizedSearch) ||
          product.name.toLowerCase().includes(normalizedSearch) ||
          (product.origin || '').toLowerCase().includes(normalizedSearch)
      )
    : allProducts;
  const totalPages = Math.max(1, Math.ceil(filteredProducts.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const start = (currentPage - 1) * pageSize;
  return {
    ...response,
    data: {
      items: filteredProducts.slice(start, start + pageSize),
      total: filteredProducts.length,
      page: currentPage,
      page_size: pageSize,
      total_pages: totalPages,
    },
  };
}

// 429 Rate Limit 재시도 (1회)
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 429 && !error.config._retried) {
      error.config._retried = true;
      const retryAfter = parseInt(error.response.headers['retry-after'], 10) || 2;
      await new Promise((r) => setTimeout(r, Math.min(retryAfter, 10) * 1000));
      return api(error.config);
    }
    return Promise.reject(error);
  },
);

export const productApi = {
  // Product Operations
  create: ({ owner_id, ...body }) => api.post('/products/', body, withOperatorAuth({ params: { owner_id } })),
  getAll: () => api.get('/products/', withOperatorAuth()),
  getPage: async ({ page = 1, pageSize = 20, search = '' } = {}) => {
    try {
      return await api.get('/products/page', withOperatorAuth({
        params: {
          page,
          page_size: pageSize,
          search: search.trim() || undefined,
        },
      }));
    } catch (error) {
      if (error.response?.status !== 404) {
        throw error;
      }
      const response = await api.get('/products/', withOperatorAuth());
      return toProductPageResponse(response, { page, pageSize, search });
    }
  },
  getById: (id) => api.get(`/products/${id}`, withOperatorAuth()),

  // Tracking & Blockchain (backend expects query params)
  addTracking: (id, data) => api.post(`/products/${id}/track`, null, withOperatorAuth({ params: data })),
  getHistory: (id) => api.get(`/products/${id}/history`, withOperatorAuth()),

  // Certifications (backend expects query params)
  addCertification: (id, data) => api.post(`/products/${id}/certifications`, null, withOperatorAuth({ params: data })),
};

export const userApi = {
  create: (data) => api.post('/users/', data, withOperatorAuth()),
};

export const analyticsApi = {
  trackQrEvent: (payload) => api.post('/qr-events', payload),
};

export const qrVerifyApi = {
  verify: (qrToken, { sessionId, variantId = 'qr_consumer_v1', source = 'consumer_verify_page' } = {}) => (
    api.get(`/api/qr/${encodeURIComponent(qrToken)}/verify`, {
      params: {
        session_id: sessionId || undefined,
        variant_id: variantId,
        source,
      },
    })
  ),
};

export const qrTokenAdminApi = {
  listByProduct: (productId, { tokenStatus = 'all', page = 1, pageSize = 20 } = {}) => (
    api.get(`/qr-tokens/products/${encodeURIComponent(productId)}`, withOperatorAuth({
      params: {
        token_status: tokenStatus,
        page,
        page_size: pageSize,
      },
    }))
  ),
  reissue: (productId, { revokeExisting = true } = {}) => (
    api.post(`/qr-tokens/products/${encodeURIComponent(productId)}/reissue`, {
      revoke_existing: revokeExisting,
    }, withOperatorAuth())
  ),
  revoke: (tokenId) => api.post(`/qr-tokens/${encodeURIComponent(tokenId)}/revoke`, null, withOperatorAuth()),
};

export const sensorDeviceAdminApi = {
  list: ({ sensorStatus = 'all', zone = '', page = 1, pageSize = 20 } = {}) => (
    api.get('/sensor-devices', withOperatorAuth({
      params: {
        sensor_status: sensorStatus,
        zone: zone.trim() || undefined,
        page,
        page_size: pageSize,
      },
    }))
  ),
  listMqttRejections: ({ windowHours = 24, sensorId = '', reason = '', page = 1, pageSize = 10 } = {}) => (
    api.get('/sensor-devices/mqtt-rejections', withOperatorAuth({
      params: {
        window_hours: windowHours,
        sensor_id: sensorId.trim() || undefined,
        reason: reason.trim() || undefined,
        page,
        page_size: pageSize,
      },
    }))
  ),
  listUnsupportedIdentities: () => api.get('/sensor-devices/unsupported-identities', withOperatorAuth()),
  disableUnsupportedIdentities: ({ sensorIds } = {}) => (
    api.post('/sensor-devices/unsupported-identities/disable', {
      sensor_ids: sensorIds,
    }, withOperatorAuth())
  ),
  reissueUnsupportedIdentity: ({ oldSensorId, newSensorId }) => (
    api.post('/sensor-devices/unsupported-identities/reissue', {
      old_sensor_id: oldSensorId.trim(),
      new_sensor_id: newSensorId.trim(),
    }, withOperatorAuth())
  ),
  getBrokerProvisioning: ({ passwordFilePath = '/etc/mosquitto/passwd', dynamicSecurityRole = 'agriguard-sensor' } = {}) => (
    api.get('/sensor-devices/mqtt-broker-provisioning', withOperatorAuth({
      params: {
        password_file_path: passwordFilePath.trim() || '/etc/mosquitto/passwd',
        dynamic_security_role: dynamicSecurityRole.trim() || 'agriguard-sensor',
      },
    }))
  ),
  getBrokerProvisioningEvidence: () => api.get('/sensor-devices/mqtt-broker-provisioning/evidence', withOperatorAuth()),
  getBrokerProvisioningEvidenceHistory: ({ brokerHost = '', page = 1, pageSize = 5 } = {}) => (
    api.get('/sensor-devices/mqtt-broker-provisioning/evidence/history', withOperatorAuth({
      params: {
        broker_host: brokerHost.trim() || undefined,
        page,
        page_size: pageSize,
      },
    }))
  ),
  recordBrokerProvisioningEvidence: ({
    mode,
    artifactHash,
    artifactGeneratedAt,
    appliedAt,
    brokerHost = '',
    runbookReference = '',
    activeSensorCount,
    disabledSensorCount,
    unsupportedSensorCount,
    credentialRotationRequired,
    rotationNote = '',
  }) => (
    api.post('/sensor-devices/mqtt-broker-provisioning/evidence', {
      mode,
      artifact_hash: artifactHash,
      artifact_generated_at: artifactGeneratedAt,
      applied_at: appliedAt,
      broker_host: brokerHost.trim() || null,
      runbook_reference: runbookReference.trim() || null,
      active_sensor_count: activeSensorCount,
      disabled_sensor_count: disabledSensorCount,
      unsupported_sensor_count: unsupportedSensorCount,
      credential_rotation_required: credentialRotationRequired,
      rotation_note: rotationNote.trim() || null,
    }, withOperatorAuth())
  ),
  upsert: (sensorId, {
    label = '',
    zone = '',
    expectedIntervalMinutes = '',
    isActive = true,
    ownerId = '',
    clearOwner = false,
  } = {}) => {
    const shouldClearOwner = Boolean(clearOwner);
    return api.put(`/sensor-devices/${encodeURIComponent(sensorId)}`, {
      label: label.trim() || null,
      zone: zone.trim() || null,
      expected_interval_minutes: expectedIntervalMinutes ? Number(expectedIntervalMinutes) : null,
      is_active: isActive,
      owner_id: shouldClearOwner ? null : ownerId.trim() || null,
      clear_owner: shouldClearOwner,
    }, withOperatorAuth());
  },
  disable: (sensorId) => api.post(`/sensor-devices/${encodeURIComponent(sensorId)}/disable`, null, withOperatorAuth()),
  reactivate: (sensorId) => api.post(`/sensor-devices/${encodeURIComponent(sensorId)}/reactivate`, null, withOperatorAuth()),
};

export default api;
