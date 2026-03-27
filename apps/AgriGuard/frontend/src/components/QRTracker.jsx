import React, { memo } from 'react';
import QRCode from 'react-qr-code';

const QRTracker = memo(function QRTracker({ productId }) {
  // Construct a URL to the product tracking page
  const trackingUrl = `${window.location.origin}/product/${productId}`;

  return (
    <div className="bg-white p-4 rounded-xl shadow-lg border-4 border-green-500 inline-block hover:shadow-xl hover:-translate-y-1 transition-all duration-300">
      <QRCode
        value={trackingUrl}
        size={128}
        bgColor="#ffffff"
        fgColor="#000000"
        level="H"
      />
      <p className="text-center text-xs font-bold text-gray-800 mt-2 font-mono tracking-wider">
        SCAN TO VERIFY
      </p>
    </div>
  );
});

export default QRTracker;
