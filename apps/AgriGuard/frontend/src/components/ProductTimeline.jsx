import React from 'react';
import { motion } from 'framer-motion';
import { Package, Truck, CheckCircle, Award } from 'lucide-react';

const ACTION_LABELS = {
  REGISTER: 'Registered',
  REGISTERED: 'Registered',
  CERTIFICATION_ISSUED: 'Certification Issued',
  IN_TRANSIT: 'In Transit',
  DELIVERED: 'Delivered',
  VERIFIED: 'Verified',
};

const FIELD_LABELS = {
  handler_id: 'Handler ID',
  owner_id: 'Owner ID',
  product_id: 'Product ID',
  qr_code: 'QR Code',
  tx_hash: 'TX Hash',
};

const MACHINE_VALUE_KEYS = new Set([
  'handler_id',
  'owner_id',
  'product_id',
  'qr_code',
  'tx_hash',
]);

const DATE_VALUE_KEYS = new Set([
  'created_at',
  'event_timestamp',
  'timestamp',
  'updated_at',
]);
const TIMELINE_LOCALE = 'en-US';

const toTitleCase = (value) =>
  value
    .toLowerCase()
    .split(/[\s_]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');

const formatEventLabel = (value) => {
  if (!value) return 'Unknown Event';
  const normalized = String(value).trim();
  return ACTION_LABELS[normalized] || toTitleCase(normalized);
};

const formatFieldLabel = (key) => FIELD_LABELS[key] || toTitleCase(key);

const formatDateTime = (value) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat(TIMELINE_LOCALE, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZoneName: 'short',
  }).format(date);
};

const formatTimelineValue = (key, value) => {
  if (value === null || value === undefined || value === '') return 'Not recorded';

  if (key === 'status' || key === 'action') {
    return formatEventLabel(value);
  }

  if (DATE_VALUE_KEYS.has(key)) {
    const formattedDate = formatDateTime(value);
    if (formattedDate) return formattedDate;
  }

  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
};

const EventIcon = ({ action }) => {
  switch (action) {
    case 'REGISTER':
    case 'REGISTERED':
      return <Package className="w-4 h-4 text-blue-400" />;
    case 'CERTIFICATION_ISSUED':
      return <Award className="w-4 h-4 text-amber-400" />;
    case 'IN_TRANSIT':
      return <Truck className="w-4 h-4 text-cyan-400" />;
    case 'DELIVERED':
    case 'VERIFIED':
      return <CheckCircle className="w-4 h-4 text-emerald-400" />;
    default:
      return <Package className="w-4 h-4 text-slate-400" />;
  }
};

export default function ProductTimeline({ history = [] }) {
  if (!history || history.length === 0) {
    return (
      <div className="p-8 text-center text-slate-400 bg-slate-950/40 rounded-2xl border border-white/5 backdrop-blur-sm">
        No tracking history available yet.
      </div>
    );
  }

  // Render in source order, which is expected to be ascending by block number
  // from oldest to newest. The final item is therefore the latest event.
  const containerVariants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.15
      }
    }
  };

  const itemVariants = {
    hidden: { opacity: 0, x: -20, y: 10 },
    show: {
      opacity: 1,
      x: 0,
      y: 0,
      transition: { type: "spring", stiffness: 100, damping: 15 }
    }
  };

  return (
    <div className="space-y-6">
      <h3 className="text-xl font-bold text-white mb-6 bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent flex items-center gap-2">
        <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
        Blockchain Tracking History
      </h3>

      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="relative ml-4 pl-1 space-y-8"
      >
        {/* Beautiful Gradient Timeline Path */}
        <div className="absolute left-[3px] top-4 bottom-4 w-[2px] bg-gradient-to-b from-indigo-500 via-purple-500 to-emerald-500 opacity-60 rounded-full" />

        {history.map((block, idx) => {
          const isLatest = idx === history.length - 1;
          const { data, timestamp, tx_hash } = block;
          const dateStr = formatDateTime(timestamp) || 'Time pending';
          const explorerUrl = block.explorer_url || data?.explorer_url || '';

          return (
            <motion.div key={tx_hash} variants={itemVariants} className="relative pl-8 group">

              {/* Timeline dot */}
              <div className="absolute -left-[15px] top-[14px] z-10 flex items-center justify-center">
                {isLatest ? (
                  <div className="relative flex items-center justify-center">
                    <span className="animate-ping absolute inline-flex h-8 w-8 rounded-full bg-emerald-500/30 opacity-75"></span>
                    <div className="relative rounded-full p-2 bg-slate-900 border border-emerald-500 shadow-[0_0_15px_rgba(16,185,129,0.5)] transition-transform duration-300 group-hover:scale-110">
                      <EventIcon action={data?.action} />
                    </div>
                  </div>
                ) : (
                  <div className="rounded-full p-2 bg-slate-900 border border-slate-700 group-hover:border-indigo-400 transition-all duration-300 group-hover:scale-110 shadow-lg">
                    <EventIcon action={data?.action} />
                  </div>
                )}
              </div>

              {/* Card Container */}
              <div className="bg-slate-900/35 border border-white/5 p-5 rounded-2xl hover:bg-slate-900/60 hover:border-white/10 hover:shadow-[0_8px_30px_rgb(0,0,0,0.15)] transition-all duration-300">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 mb-3">
                  <div className="flex items-center gap-3">
                    <span className={`px-2.5 py-0.5 rounded text-xs font-bold font-mono tracking-wider ${isLatest ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-slate-800 text-slate-300 border border-slate-700/50'}`}>
                      BLOCK #{block.block}
                    </span>
                    <h4 className="text-base font-bold text-slate-100 group-hover:text-white transition-colors">
                      {formatEventLabel(data?.action)}
                    </h4>
                  </div>
                  <span className="text-xs font-mono text-slate-400 bg-slate-950/40 px-2 py-1 rounded border border-white/5">{dateStr}</span>
                </div>

                <div className="space-y-2 mt-3 bg-slate-950/20 p-3.5 rounded-xl border border-white/5">
                  {Object.entries(data).map(([key, value]) => {
                    if (key === 'action' || key === 'explorer_url') return null;
                    const formattedValue = formatTimelineValue(key, value);
                    const machineValue = MACHINE_VALUE_KEYS.has(key);
                    return (
                      <div key={key} className="flex flex-col gap-1 text-xs sm:flex-row sm:gap-2">
                        <span className="font-semibold text-slate-400 sm:min-w-[100px]">{formatFieldLabel(key)}:</span>
                        <span
                          data-testid={`timeline-data-value-${key}`}
                          className={`min-w-0 break-all text-slate-200 select-all ${machineValue ? 'font-mono' : 'font-medium'}`}
                        >
                          {formattedValue}
                        </span>
                      </div>
                    );
                  })}
                </div>

                <div className="mt-4 flex flex-col gap-2 border-t border-white/5 pt-3 sm:flex-row sm:items-center sm:justify-between">
                  <p
                    data-testid="timeline-tx-hash"
                    className="min-w-0 break-all text-[10px] font-mono text-slate-500 select-all group-hover:text-slate-400 transition-colors"
                  >
                    TX: {tx_hash}
                  </p>
                  {explorerUrl ? (
                    <a
                      href={explorerUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex shrink-0 text-[10px] font-medium text-indigo-400/80 hover:underline"
                    >
                      Verify link
                    </a>
                  ) : (
                    <span
                      data-testid="timeline-tx-status"
                      className="inline-flex shrink-0 text-[10px] font-medium text-slate-400"
                    >
                      TX recorded
                    </span>
                  )}
                </div>
              </div>
            </motion.div>
          );
        })}
      </motion.div>
    </div>
  );
}
