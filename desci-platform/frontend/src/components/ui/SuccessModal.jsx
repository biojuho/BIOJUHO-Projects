import { motion, AnimatePresence } from 'framer-motion';
import { X, CheckCircle, ExternalLink } from 'lucide-react';
import { useLocale } from '../../contexts/LocaleContext';

const SuccessModal = ({ isOpen, onClose, title, message, txHash }) => {
  const { t } = useLocale();
  if (!isOpen) return null;

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-[#f2eadf]/70 p-4 backdrop-blur-md"
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.92, y: 18 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.92, y: 18 }}
            transition={{ type: 'spring', duration: 0.45, bounce: 0.2 }}
            className="glass-card relative w-full max-w-md p-8"
            onClick={(event) => event.stopPropagation()}
          >
            <button
              onClick={onClose}
              className="absolute right-5 top-5 rounded-full p-2 text-ink-muted transition-colors hover:bg-white/70 hover:text-ink"
            >
              <X size={18} />
            </button>

            <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-success/12 text-success shadow-clay-soft">
              <CheckCircle size={38} strokeWidth={2.4} />
            </div>

            <h2 className="mb-3 text-center font-display text-3xl font-semibold text-ink">
              {title || t('common.result')}
            </h2>
            <p className="mb-6 text-center text-sm leading-7 text-ink-muted">
              {message || t('common.noData')}
            </p>

            {txHash && (
              <div className="clay-panel-pressed mb-6 flex items-center justify-between gap-3 rounded-[1.6rem] p-4">
                <div className="min-w-0">
                  <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-ink-soft">{t('proposal.txHash')}</p>
                  <p className="truncate font-mono text-sm text-info-dark">{txHash}</p>
                </div>
                <ExternalLink size={16} className="shrink-0 text-ink-soft" />
              </div>
            )}

            <button onClick={onClose} className="clay-button clay-button-primary w-full justify-center text-white">
              {t('common.close')}
            </button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default SuccessModal;
