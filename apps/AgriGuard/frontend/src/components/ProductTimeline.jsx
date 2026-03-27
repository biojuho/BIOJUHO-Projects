import React from 'react';
import { motion } from 'framer-motion';
import { Package, Truck, CheckCircle, Award } from 'lucide-react';

const EventIcon = ({ action }) => {
  switch (action) {
    case 'REGISTER':
      return <Package className="w-5 h-5 text-blue-400" />;
    case 'CERTIFICATION_ISSUED':
      return <Award className="w-5 h-5 text-yellow-400" />;
    case 'IN_TRANSIT':
      return <Truck className="w-5 h-5 text-orange-400" />;
    case 'DELIVERED':
    case 'VERIFIED':
      return <CheckCircle className="w-5 h-5 text-green-400" />;
    default:
      return <Package className="w-5 h-5 text-gray-400" />;
  }
};

export default function ProductTimeline({ history = [] }) {
  if (!history || history.length === 0) {
    return (
      <div className="p-8 text-center text-gray-400 bg-white/5 rounded-2xl border border-white/10">
        No tracking history available yet.
      </div>
    );
  }

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
    hidden: { opacity: 0, x: -25, y: 10 },
    show: { 
      opacity: 1, 
      x: 0, 
      y: 0,
      transition: { type: "spring", stiffness: 100, damping: 15 } 
    }
  };

  return (
    <div className="space-y-6">
      <h3 className="text-xl font-bold text-white mb-6">Blockchain Tracking History</h3>
      <motion.div 
        variants={containerVariants} 
        initial="hidden" 
        animate="show" 
        className="relative border-l border-white/20 ml-4 space-y-8"
      >
        {history.map((block, idx) => {
          const isLatest = idx === history.length - 1;
          const { data, timestamp, tx_hash } = block;
          const dateStr = new Date(timestamp).toLocaleString();

          return (
            <motion.div key={tx_hash} variants={itemVariants} className="relative pl-8">
              {/* Timeline dot */}
              <div className={`absolute -left-[18px] top-1 rounded-full p-1.5 border-4 border-gray-900 ${isLatest ? 'bg-green-500 shadow-[0_0_15px_rgba(34,197,94,0.5)]' : 'bg-white/20'}`}>
                 <EventIcon action={data?.action} />
              </div>
              
              <div className="bg-white/5 border border-white/10 p-5 rounded-2xl hover:bg-white/10 transition-colors">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 mb-3">
                  <div className="flex items-center gap-3">
                    <span className={`px-2.5 py-1 rounded text-xs font-bold ${isLatest ? 'bg-green-500/20 text-green-400' : 'bg-white/10 text-gray-300'}`}>
                      Block #{block.block}
                    </span>
                    <h4 className="text-lg font-semibold text-white">
                      {data?.action || 'UNKNOWN EVENT'}
                    </h4>
                  </div>
                  <span className="text-sm font-mono text-gray-400">{dateStr}</span>
                </div>
                
                <div className="space-y-2">
                  {Object.entries(data).map(([key, value]) => {
                    if (key === 'action') return null;
                    return (
                      <div key={key} className="flex gap-2 text-sm text-gray-300">
                        <span className="font-semibold text-gray-400 min-w-[100px] capitalize">{key.replace('_', ' ')}:</span>
                        <span className="text-white">{value}</span>
                      </div>
                    );
                  })}
                </div>

                <div className="mt-4 pt-4 border-t border-white/10">
                  <p className="text-xs font-mono text-gray-500 truncate group cursor-pointer hover:text-gray-300 transition-colors">
                    TX: {tx_hash}
                  </p>
                </div>
              </div>
            </motion.div>
          );
        })}
      </motion.div>
    </div>
  );
}
