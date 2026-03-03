import { useState } from 'react';
import { Scanner } from '@yudiel/react-qr-scanner';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Camera, AlertCircle, ScanLine, CheckCircle } from 'lucide-react';
import { Card, CardContent } from './ui/Card';

export default function QRReader() {
  const [error, setError] = useState('');
  const [isScanning, setIsScanning] = useState(true);
  const [scanSuccess, setScanSuccess] = useState(false);
  const navigate = useNavigate();

  const handleScan = (detectedCodes) => {
    if (detectedCodes && detectedCodes.length > 0) {
      const code = detectedCodes[0].rawValue;
      setIsScanning(false);

      try {
        const url = new URL(code);
        const pathSegments = url.pathname.split('/');
        const productIndex = pathSegments.indexOf('product');
        if (productIndex !== -1 && pathSegments.length > productIndex + 1) {
          const productId = pathSegments[productIndex + 1];
          setScanSuccess(true);
          setTimeout(() => navigate(`/product/${productId}`), 1200);
        } else {
          throw new Error('AgriGuard 제품 URL 형식이 아닙니다.');
        }
      } catch {
        setError('유효하지 않은 QR 코드입니다. AgriGuard 제품 QR을 스캔해주세요.');
        setTimeout(() => {
          setIsScanning(true);
          setError('');
        }, 3000);
      }
    }
  };

  return (
    <div className="max-w-md mx-auto mt-8 animate-in fade-in duration-500">
      <Card className="shadow-xl overflow-hidden">
        
        {/* Header Section */}
        <div className="bg-gradient-to-r from-primary to-emerald-600 p-6 text-center">
          <div className="mx-auto bg-white/20 w-16 h-16 rounded-full flex items-center justify-center mb-4">
            <ScanLine className="w-8 h-8 text-white" />
          </div>
          <h2 className="text-2xl font-bold text-white">제품 스캔하기</h2>
          <p className="text-white/80 mt-2 text-sm">
            카메라를 사용하여 제품에 부착된 QR 코드를 스캔하세요.
          </p>
        </div>

        {/* Camera Scanner Viewport */}
        <CardContent className="p-6">
          <div className="relative aspect-square w-full rounded-xl overflow-hidden border-2 border-border bg-muted flex items-center justify-center">
            {isScanning ? (
               <Scanner
                  onScan={handleScan}
                  onError={(err) => setError(`카메라 오류: ${err.message}`)}
                  components={{
                    audio: false,
                    onOff: true,
                    torch: true,
                    zoom: true,
                    finder: true
                  }}
                  styles={{
                    container: { width: '100%', height: '100%', borderRadius: '12px' },
                    video: { objectFit: 'cover' }
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
                <p className="text-lg font-bold text-primary">스캔 성공!</p>
                <p className="text-sm text-muted-foreground mt-1">제품 정보를 불러오는 중...</p>
              </motion.div>
            ) : (
              <div className="text-center text-muted-foreground">
                <Camera className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm font-medium">스캔 처리 중...</p>
              </div>
            )}
          </div>

          {/* Feedback/Error State */}
          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="mt-4 p-4 rounded-lg bg-destructive/10 flex items-start gap-3 border border-destructive/20"
              >
                <AlertCircle className="w-5 h-5 text-destructive shrink-0 mt-0.5" />
                <p className="text-sm text-destructive font-medium">{error}</p>
              </motion.div>
            )}
          </AnimatePresence>

          <div className="mt-6 text-center pb-2">
            <p className="text-xs text-muted-foreground">
              어두운 곳에서는 화면 우측 하단의 <br/>플래시 버튼을 활용해 보세요.
            </p>
          </div>
        </CardContent>

      </Card>
    </div>
  );
}
