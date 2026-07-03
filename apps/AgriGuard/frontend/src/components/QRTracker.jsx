import React, { memo } from 'react';
import { QRCode } from 'react-qr-code';

const QRTracker = memo(function QRTracker({
  productId,
  value,
  ariaLabel = 'Product verification QR',
  caption = 'SCAN TO VERIFY',
}) {
  const trackingUrl = value || `${window.location.origin}/product/${productId}`;

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
