import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, CheckCircle, ExternalLink } from "lucide-react";

const SuccessModal = ({ isOpen, onClose, title, message, txHash }) => {
  if (!isOpen) return null;

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
            onClick={onClose}
          >
            {/* Modal Content */}
            <motion.div
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              transition={{ type: "spring", duration: 0.5, bounce: 0.3 }}
              className="relative w-full max-w-md p-6 m-4 overflow-hidden text-center bg-white/10 border border-white/20 rounded-2xl shadow-2xl backdrop-blur-xl"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Background Glow Effect */}
              <div className="absolute -top-20 -left-20 w-40 h-40 bg-purple-500/30 rounded-full blur-3xl pointer-events-none" />
              <div className="absolute -bottom-20 -right-20 w-40 h-40 bg-blue-500/30 rounded-full blur-3xl pointer-events-none" />

              {/* Close Button */}
              <button
                onClick={onClose}
                className="absolute top-4 right-4 text-white/60 hover:text-white transition-colors"
              >
                <X size={20} />
              </button>

              {/* Icon Animation */}
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: 0.2, type: "spring", stiffness: 200 }}
                className="flex items-center justify-center w-20 h-20 mx-auto mb-6 bg-green-500/20 rounded-full text-green-400 border border-green-500/30 shadow-[0_0_30px_rgba(74,222,128,0.3)]"
              >
                <CheckCircle size={40} strokeWidth={2.5} />
              </motion.div>

              {/* Content */}
              <motion.h2
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
                className="mb-2 text-2xl font-bold text-white tracking-tight"
              >
                {title || "Success!"}
              </motion.h2>

              <motion.p
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 }}
                className="mb-6 text-slate-300 leading-relaxed"
              >
                {message || "Operation completed successfully."}
              </motion.p>

              {/* Transaction Hash */}
              {txHash && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.5 }}
                  className="mb-6"
                >
                  <div className="p-3 bg-black/20 rounded-lg border border-white/10 flex items-center justify-between group cursor-pointer hover:bg-black/30 transition-colors">
                    <div className="flex flex-col items-start overflow-hidden">
                      <span className="text-xs text-slate-400 mb-0.5 uppercase tracking-wider font-semibold">
                        Transaction Hash
                      </span>
                      <span className="text-sm text-blue-300 font-mono truncate w-full max-w-[200px] sm:max-w-xs block">
                        {txHash}
                      </span>
                    </div>
                    <ExternalLink
                      size={16}
                      className="text-slate-400 group-hover:text-white transition-colors flex-shrink-0 ml-2"
                    />
                  </div>
                </motion.div>
              )}

              {/* Action Button */}
              <motion.button
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.6 }}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={onClose}
                className="w-full py-3.5 px-6 font-semibold text-white bg-gradient-to-r from-blue-600 to-purple-600 rounded-xl shadow-lg hover:shadow-indigo-500/25 transition-all duration-300"
              >
                확인
              </motion.button>
            </motion.div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

export default SuccessModal;
