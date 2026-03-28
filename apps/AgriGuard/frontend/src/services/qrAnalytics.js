import { analyticsApi } from './api';

export const QR_EXPERIMENT_VARIANT = 'qr_page_v1';

export function createQrSessionId() {
  return `qr-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export function normalizeScannerError(error) {
  if (!error) {
    return { error_code: 'unknown_error', error_message: 'Unknown scanner error' };
  }

  const message = typeof error === 'string' ? error : error.message || 'Unknown scanner error';
  const lower = message.toLowerCase();
  if (lower.includes('permission')) {
    return { error_code: 'camera_permission_denied', error_message: message };
  }
  if (lower.includes('notfound') || lower.includes('device')) {
    return { error_code: 'camera_not_found', error_message: message };
  }
  return { error_code: 'scanner_runtime_error', error_message: message };
}

export async function trackQrEvent(event) {
  try {
    await analyticsApi.trackQrEvent({
      source: 'qr_reader',
      variant_id: QR_EXPERIMENT_VARIANT,
      occurred_at: new Date().toISOString(),
      event_payload: {},
      ...event,
    });
    return true;
  } catch (error) {
    console.error('Failed to track QR event', error);
    return false;
  }
}
