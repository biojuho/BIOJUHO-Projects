import React, { useState } from 'react';
import { Scanner } from '@yudiel/react-qr-scanner';
import { useNavigate } from 'react-router-dom';
import { Camera, AlertCircle, ScanLine } from 'lucide-react';

export default function QRReader() {
  const [error, setError] = useState('');
  const [isScanning, setIsScanning] = useState(true);
  const navigate = useNavigate();

  const handleScan = (detectedCodes) => {
    if (detectedCodes && detectedCodes.length > 0) {
      const code = detectedCodes[0].rawValue;
      
      // Stop scanning to prevent multiple triggers
      setIsScanning(false);

      try {
        // We expect URLs formatted as: http://domain.com/product/{productId}
        const url = new URL(code);
        const pathSegments = url.pathname.split('/');
        
        // Find 'product' in the path and get the next segment as ID
        const productIndex = pathSegments.indexOf('product');
        if (productIndex !== -1 && pathSegments.length > productIndex + 1) {
          const productId = pathSegments[productIndex + 1];
          // Navigate to the correct internal Product Detail relative path
          navigate(`/product/${productId}`);
        } else {
          throw new Error('AgriGuard 제품 URL 형식이 아닙니다.');
        }
      } catch {
        setError('유효하지 않은 QR 코드입니다. AgriGuard 제품 QR을 스캔해주세요.');
        // Resume scanning after a brief error timeout so user can try again
        setTimeout(() => {
          setIsScanning(true);
          setError('');
        }, 3000);
      }
    }
  };

  return (
    <div className="max-w-md mx-auto mt-8 animate-in fade-in duration-500">
      <div className="bg-white rounded-2xl border border-slate-100 shadow-xl overflow-hidden">
        
        {/* Header Section */}
        <div className="bg-gradient-to-r from-emerald-600 to-teal-500 p-6 text-center">
          <div className="mx-auto bg-white/20 w-16 h-16 rounded-full flex items-center justify-center mb-4">
            <ScanLine className="w-8 h-8 text-white" />
          </div>
          <h2 className="text-2xl font-bold text-white">제품 스캔하기</h2>
          <p className="text-emerald-50 mt-2 text-sm">
            카메라를 사용하여 제품에 부착된 QR 코드를 스캔하세요.
          </p>
        </div>

        {/* Camera Scanner Viewport */}
        <div className="p-6">
          <div className="relative aspect-square w-full rounded-xl overflow-hidden border-2 border-slate-200 bg-slate-50 flex items-center justify-center">
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
            ) : (
              <div className="text-center text-slate-500">
                <Camera className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm font-medium">스캔 처리 중...</p>
              </div>
            )}
          </div>

          {/* Feedback/Error State */}
          {error && (
            <div className="mt-4 p-4 rounded-lg bg-red-50 flex items-start gap-3 border border-red-100">
              <AlertCircle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
              <p className="text-sm text-red-700 font-medium">{error}</p>
            </div>
          )}

          <div className="mt-6 text-center pb-2">
            <p className="text-xs text-slate-400">
              어두운 곳에서는 화면 우측 하단의 <br/>플래시 버튼을 활용해 보세요.
            </p>
          </div>
        </div>

      </div>
    </div>
  );
}
