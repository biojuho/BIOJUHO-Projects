import { useEffect, useRef, useState } from 'react';
import { Scanner } from '@yudiel/react-qr-scanner';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Camera, AlertCircle, ScanLine, CheckCircle, RefreshCcw } from 'lucide-react';
import { Card, CardContent } from './ui/Card';
import { Button } from './ui/Button';
import { useToast } from '../contexts/ToastContext';
import {
  createQrSessionId,
  normalizeScannerError,
  QR_EXPERIMENT_VARIANT,
  trackQrEvent,
} from '../services/qrAnalytics';

const SCAN_SOURCE = 'qr_reader';

export default function QRReader() {
  const [error, setError] = useState('');
  const [isScanning, setIsScanning] = useState(true);
  const [scanSuccess, setScanSuccess] = useState(false);
  const [attempt, setAttempt] = useState(1);
  const [lastQrValue, setLastQrValue] = useState('');
  const [sessionId] = useState(() => createQrSessionId());
  const failureSignatureRef = useRef('');
  const navigate = useNavigate();
  const { showToast } = useToast();

  useEffect(() => {
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
    setError('');
    setScanSuccess(false);
    setIsScanning(true);
    setAttempt((current) => current + 1);
  };

  const handleScan = (detectedCodes) => {
    if (!isScanning || !detectedCodes || detectedCodes.length === 0) {
      return;
    }

    const code = detectedCodes[0]?.rawValue?.trim();
    if (!code) {
      return;
    }

    setLastQrValue(code);
    setIsScanning(false);

    try {
      const url = new URL(code);
      const pathSegments = url.pathname.split('/');
      const productIndex = pathSegments.indexOf('product');
      if (productIndex === -1 || pathSegments.length <= productIndex + 1) {
        throw new Error('This QR code does not contain a valid AgriGuard product route.');
      }

      const productId = pathSegments[productIndex + 1];
      setScanSuccess(true);
      showToast('Verification in progress', 'success');
      window.setTimeout(() => {
        navigate(
          `/product/${productId}?scan_source=${SCAN_SOURCE}&scan_session=${sessionId}&scan_variant=${QR_EXPERIMENT_VARIANT}`,
        );
      }, 1200);
    } catch {
      void handleFailure({
        message: 'This QR code is not a valid AgriGuard product link.',
        errorCode: 'invalid_qr_format',
        qrValue: code,
      });
      showToast('Invalid AgriGuard QR code', 'error');
    }
  };

  return (
    <div className="max-w-md mx-auto mt-8 animate-in fade-in duration-500">
      <Card className="shadow-xl overflow-hidden">
        <div className="bg-gradient-to-r from-primary to-emerald-600 p-6 text-center">
          <div className="mx-auto bg-white/20 w-16 h-16 rounded-full flex items-center justify-center mb-4">
            <ScanLine className="w-8 h-8 text-white" />
          </div>
          <h2 className="text-2xl font-bold text-white">Scan Product QR</h2>
          <p className="text-white/80 mt-2 text-sm">
            Point the camera at an AgriGuard verification QR to open the product journey.
          </p>
        </div>

        <CardContent className="p-6">
          <div className="relative aspect-square w-full rounded-xl overflow-hidden border-2 border-border bg-muted flex items-center justify-center">
            {isScanning ? (
              <Scanner
                onScan={handleScan}
                onError={(scannerError) => {
                  const normalized = normalizeScannerError(scannerError);
                  void handleFailure({
                    message: `Camera error: ${normalized.error_message}`,
                    errorCode: normalized.error_code,
                  });
                  showToast('Camera access failed', 'error');
                }}
                components={{
                  audio: false,
                  onOff: true,
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
                <p className="text-xs mt-2">Use retry to recover from camera or QR recognition issues.</p>
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
