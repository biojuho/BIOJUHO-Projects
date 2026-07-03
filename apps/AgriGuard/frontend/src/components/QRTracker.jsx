import React, { memo } from 'react';
import { QRCode } from 'react-qr-code';

const QRTracker = memo(function QRTracker({
  productId,
  value,
  ariaLabel = 'Product verification QR',
  caption = 'SCAN TO VERIFY',
}) {
  const explicitValue = String(value || '').trim();
  const productIdValue = String(productId || '').trim();
  const trackingUrl = explicitValue || (productIdValue ? `${window.location.origin}/product/${productIdValue}` : '');

  if (!trackingUrl) {
    return (
      <div
        role="status"
        aria-label="Product verification QR unavailable"
        className="bg-white p-4 rounded-xl shadow-lg border-4 border-gray-300 inline-flex min-h-[184px] min-w-[184px] flex-col items-center justify-center text-gray-700"
      >
        <div className="flex h-32 w-32 items-center justify-center rounded-lg border border-dashed border-gray-300 bg-gray-50 text-xs font-bold tracking-wider">
          QR
        </div>
        <p className="text-center text-xs font-bold text-gray-700 mt-2 font-mono tracking-wider">
          QR UNAVAILABLE
        </p>
      </div>
    );
  }

  return (
    <div
      role="img"
      aria-label={ariaLabel}
      className="bg-white p-4 rounded-xl shadow-lg border-4 border-green-500 inline-block hover:shadow-xl hover:-translate-y-1 transition-all duration-300"
    >
      <QRCode
        value={trackingUrl}
        size={128}
        bgColor="#ffffff"
        fgColor="#000000"
        level="H"
      />
      <p className="text-center text-xs font-bold text-gray-800 mt-2 font-mono tracking-wider">
        {caption}
      </p>
    </div>
  );
});

export default QRTracker;
