import { useEffect, useRef, useState } from 'react';
import { Scanner } from '@yudiel/react-qr-scanner';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Camera, AlertCircle, ScanLine, CheckCircle, RefreshCcw, Keyboard, X } from 'lucide-react';
import { Card, CardContent } from './ui/Card';
import { Button } from './ui/Button';
import { Input } from './ui/Input';
import { useToast } from '../contexts/ToastContext';
import {
  createQrSessionId,
  normalizeScannerError,
  QR_EXPERIMENT_VARIANT,
  trackQrEvent,
} from '../services/qrAnalytics';

const SCAN_SOURCE = 'qr_reader';

function extractTokenFromUrl(url) {
  if (url.protocol === 'agri:' && url.hostname === 'verify') {
    return url.pathname.replace(/^\/+/, '');
  }

  const pathSegments = url.pathname.split('/').filter(Boolean);
  for (const marker of ['verify', 'product']) {
    const markerIndex = pathSegments.indexOf(marker);
    if (markerIndex !== -1 && pathSegments.length > markerIndex + 1) {
      return pathSegments[markerIndex + 1];
    }
  }

  return '';
}

function extractVerificationToken(rawValue, { allowBareToken = false } = {}) {
  const code = rawValue?.trim();
  if (!code) {
    return '';
  }

  try {
    return extractTokenFromUrl(new URL(code));
  } catch {
    if (!allowBareToken) {
      return '';
    }
  }

  if (code.startsWith('/')) {
    try {
      return extractTokenFromUrl(new URL(code, 'https://agriguard.local'));
    } catch {
      return '';
    }
  }

  if (/^[A-Za-z0-9_-][A-Za-z0-9._:-]{3,159}$/.test(code)) {
    return code;
  }

  return '';
}

function createVerificationPath(qrToken, sessionId) {
  return `/verify/${encodeURIComponent(qrToken)}?scan_source=${SCAN_SOURCE}&scan_session=${sessionId}&scan_variant=${QR_EXPERIMENT_VARIANT}`;
}

function clearNavigationTimer(timerRef) {
  if (timerRef.current) {
    window.clearTimeout(timerRef.current);
    timerRef.current = null;
  }
}

const MANUAL_INPUT_ID = 'manual-qr-value';
const MANUAL_HELP_ID = 'manual-qr-help';
const NAVIGATION_DELAY_MS = 1200;

function normalizeManualValue(value) {
  return value.trim();
}

function hasManualValue(value) {
  return normalizeManualValue(value).length > 0;
}

function getManualFailureMessage(value) {
  if (!hasManualValue(value)) {
    return 'Enter a verification link or token before continuing.';
  }

  return 'Enter a valid AgriGuard verification link or token.';
}

export default function QRReader() {
  const [error, setError] = useState('');
  const [isScanning, setIsScanning] = useState(true);
  const [scanSuccess, setScanSuccess] = useState(false);
  const [attempt, setAttempt] = useState(1);
  const [lastQrValue, setLastQrValue] = useState('');
  const [manualQrValue, setManualQrValue] = useState('');
  const [sessionId] = useState(() => createQrSessionId());
  const failureSignatureRef = useRef('');
  const navigationTimerRef = useRef(null);
  const scanStartTrackedAttemptRef = useRef(null);
  const scanHandledRef = useRef(false);
  const navigate = useNavigate();
  const { showToast, hideToast } = useToast();
  const manualValueReady = hasManualValue(manualQrValue);

  useEffect(() => () => {
    clearNavigationTimer(navigationTimerRef);
  }, []);

  useEffect(() => {
    if (scanStartTrackedAttemptRef.current === attempt) {
      return;
    }
    scanStartTrackedAttemptRef.current = attempt;

    void trackQrEvent({
      session_id: sessionId,
      event_type: 'scan_start',
      event_payload: {
        attempt,
      },
    });
  }, [attempt, sessionId]);

  const handleFailure = async ({ message, errorCode, qrValue = '' }) => {
    setLastQrValue(qrValue);
    setIsScanning(false);
    setScanSuccess(false);
    setError(message);

    const signature = `${errorCode}:${message}:${qrValue}`;
    if (failureSignatureRef.current === signature) {
      return;
    }
    failureSignatureRef.current = signature;

    await trackQrEvent({
      session_id: sessionId,
      event_type: 'scan_failure',
      qr_value: qrValue || undefined,
      error_code: errorCode,
      error_message: message,
      event_payload: {
        attempt,
      },
    });
  };

  const handleRetry = async () => {
    clearNavigationTimer(navigationTimerRef);

    await trackQrEvent({
      session_id: sessionId,
      event_type: 'scan_recovery',
      recovery_method: 'retry_button',
      qr_value: lastQrValue || undefined,
      event_payload: {
        previous_attempt: attempt,
        next_attempt: attempt + 1,
      },
    });

    failureSignatureRef.current = '';
    scanHandledRef.current = false;
    setError('');
    setScanSuccess(false);
    setIsScanning(true);
    setAttempt((current) => current + 1);
  };

  const handleScan = (detectedCodes) => {
    if (scanHandledRef.current || !isScanning || !detectedCodes || detectedCodes.length === 0) {
      return;
    }

    const code = detectedCodes[0]?.rawValue?.trim();
    if (!code) {
      return;
    }

    scanHandledRef.current = true;
    setLastQrValue(code);
    setIsScanning(false);

    try {
      const qrToken = extractVerificationToken(code);
      if (!qrToken) {
        throw new Error('This QR code does not contain a valid AgriGuard product route.');
      }

      setScanSuccess(true);
      hideToast();
      showToast('Verification in progress', 'success');
      navigationTimerRef.current = window.setTimeout(() => {
        navigate(createVerificationPath(qrToken, sessionId));
        navigationTimerRef.current = null;
      }, NAVIGATION_DELAY_MS);
    } catch {
      void handleFailure({
        message: 'This QR code is not a valid AgriGuard product link.',
        errorCode: 'invalid_qr_format',
        qrValue: code,
      });
      showToast('Invalid AgriGuard QR code', 'error');
    }
  };

  const handleManualSubmit = async (event) => {
    event.preventDefault();

    const normalizedManualValue = normalizeManualValue(manualQrValue);
    const qrToken = extractVerificationToken(normalizedManualValue, { allowBareToken: true });
    if (!qrToken) {
      await handleFailure({
        message: getManualFailureMessage(normalizedManualValue),
        errorCode: 'manual_qr_format',
        qrValue: normalizedManualValue,
      });
      showToast('Invalid AgriGuard code', 'error');
      return;
    }

    clearNavigationTimer(navigationTimerRef);
    failureSignatureRef.current = '';
    scanHandledRef.current = true;
    setLastQrValue(normalizedManualValue);
    setError('');
    setIsScanning(false);
    setScanSuccess(true);

    void trackQrEvent({
      session_id: sessionId,
      event_type: 'scan_recovery',
      recovery_method: 'manual_entry',
      qr_value: normalizedManualValue,
      event_payload: {
        previous_attempt: attempt,
        next_attempt: attempt,
      },
    });

    hideToast();
    showToast('Verification in progress', 'success');
    navigate(createVerificationPath(qrToken, sessionId));
  };

  const handleManualClear = () => {
    setManualQrValue('');
  };

  return (
    <div className="max-w-md mx-auto mt-8 animate-in fade-in duration-500">
      <Card className="shadow-xl overflow-hidden">
        <div className="bg-gradient-to-r from-primary to-emerald-600 p-6 text-center">
          <div className="mx-auto bg-white/20 w-16 h-16 rounded-full flex items-center justify-center mb-4">
            <ScanLine className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white">Scan Product QR</h1>
          <p className="text-white/80 mt-2 text-sm">
            Point the camera at an AgriGuard verification QR to open the product journey.
          </p>
        </div>

        <CardContent className="p-6">
          <div data-testid="scanner-frame" className="relative mx-auto aspect-square w-full max-w-[248px] rounded-xl overflow-hidden border-2 border-border bg-muted flex items-center justify-center sm:max-w-none">
            {isScanning ? (
              <Scanner
                onScan={handleScan}
                onError={(scannerError) => {
                  if (scanHandledRef.current || !isScanning) {
                    return;
                  }
                  const normalized = normalizeScannerError(scannerError);
                  void handleFailure({
                    message: `Camera error: ${normalized.error_message}`,
                    errorCode: normalized.error_code,
                  });
                }}
                components={{
                  audio: false,
                  onOff: false,
                  torch: true,
                  zoom: true,
                  finder: true,
                }}
                styles={{
                  container: { width: '100%', height: '100%', borderRadius: '12px' },
                  video: { objectFit: 'cover' },
                }}
              />
            ) : scanSuccess ? (
              <motion.div
                initial={{ scale: 0, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ type: 'spring', stiffness: 200, damping: 15 }}
                className="text-center"
              >
                <motion.div
                  animate={{ scale: [1, 1.2, 1] }}
                  transition={{ duration: 0.8, repeat: Infinity }}
                >
                  <CheckCircle className="w-16 h-16 mx-auto mb-3 text-primary" />
                </motion.div>
                <p className="text-lg font-bold text-primary">Scan accepted</p>
                <p className="text-sm text-muted-foreground mt-1">Loading verified product details...</p>
              </motion.div>
            ) : (
              <div className="text-center text-muted-foreground px-6">
                <Camera className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm font-medium">Scanner paused</p>
                <p className="text-xs mt-2">Use retry or enter the verification token manually.</p>
              </div>
            )}
          </div>

          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="mt-4 p-4 rounded-lg bg-destructive/10 border border-destructive/20"
              >
                <div className="flex items-start gap-3">
                  <AlertCircle className="w-5 h-5 text-destructive shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <p className="text-sm text-destructive font-medium">{error}</p>
                    <p className="text-xs text-muted-foreground mt-2">
                      Session {sessionId.slice(-8)} · Attempt {attempt}
                    </p>
                  </div>
                </div>
                <div className="mt-4 flex justify-end">
                  <Button type="button" onClick={handleRetry} className="bg-emerald-600 hover:bg-emerald-700">
                    <RefreshCcw className="w-4 h-4" />
                    Retry scan
                  </Button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <form onSubmit={handleManualSubmit}>
            <div className="mt-5 rounded-lg border border-border bg-muted/30 p-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                <Keyboard className="w-4 h-4 text-primary" />
                <span>No camera?</span>
              </div>
              <label className="mt-4 block text-sm font-medium text-foreground" htmlFor={MANUAL_INPUT_ID}>
                Manual verification code
              </label>
              <div className="relative mt-2">
                <Input
                  id={MANUAL_INPUT_ID}
                  aria-describedby={MANUAL_HELP_ID}
                  autoCapitalize="none"
                  autoComplete="off"
                  className={`min-h-11 bg-background text-base sm:text-sm ${manualValueReady ? 'pr-12' : ''}`}
                  enterKeyHint="go"
                  inputMode="text"
                  placeholder="Paste /verify link or token"
                  spellCheck={false}
                  value={manualQrValue}
                  onChange={(event) => setManualQrValue(event.target.value)}
                />
                {manualValueReady && (
                  <button
                    type="button"
                    aria-label="Clear manual verification code"
                    title="Clear manual verification code"
                    onClick={handleManualClear}
                    className="absolute right-1 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <X className="h-4 w-4" aria-hidden="true" />
                  </button>
                )}
              </div>
              <p className="mt-2 text-xs leading-relaxed text-muted-foreground" id={MANUAL_HELP_ID}>
                Use this when the camera is unavailable or the QR surface is damaged.
              </p>
              <Button
                className={`mt-3 w-full ${
                  manualValueReady
                    ? 'bg-emerald-600 hover:bg-emerald-700'
                    : 'bg-muted text-muted-foreground hover:bg-muted'
                }`}
                disabled={!manualValueReady}
                type="submit"
              >
                Verify code
              </Button>
            </div>
          </form>

          <div className="mt-6 text-center pb-2">
            <p className="text-xs text-muted-foreground">
              For stable results, keep the QR fully inside the frame and avoid glare.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
