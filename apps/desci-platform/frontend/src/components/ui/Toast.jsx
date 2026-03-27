import { useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react';

const MotionDiv = motion.div;

const icons = {
    success: CheckCircle,
    error: AlertCircle,
    warning: AlertTriangle,
    info: Info,
};

const styles = {
    success: 'bg-[#f2fcf7] text-[#2c7b64] border-[#cfe9de]',
    error: 'bg-[#fff5f1] text-[#b45f53] border-[#f0c6bf]',
    warning: 'bg-[#fff8ef] text-[#b07b3c] border-[#efd7b5]',
    info: 'bg-[#f2f6ff] text-[#5f77b0] border-[#d4def9]',
};

export default function Toast({
    message,
    type = 'info',
    onClose,
    duration = 4000,
    action,
    actionLabel = 'Undo',
    onAction,
    closeLabel = 'Dismiss notification',
}) {
    const handleClose = useCallback(() => {
        onClose?.();
    }, [onClose]);

    useEffect(() => {
        if (!duration || duration <= 0) {
            return undefined;
        }

        const timer = setTimeout(handleClose, duration);
        return () => clearTimeout(timer);
    }, [duration, handleClose]);

    useEffect(() => {
        const handleKeyDown = (event) => {
            if (event.key === 'Escape') {
                handleClose();
            }
        };

        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, [handleClose]);

    const Icon = icons[type];

    return (
        <AnimatePresence>
            {message && (
                <MotionDiv
                    role="alert"
                    aria-live={type === 'error' ? 'assertive' : 'polite'}
                    aria-atomic="true"
                    className={`fixed top-6 right-4 z-50 flex min-w-[280px] max-w-[90vw] items-start gap-3 rounded-[1.6rem] border px-5 py-4 shadow-clay ${styles[type]}`}
                    initial={{ opacity: 0, y: -16, scale: 0.96 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -16, scale: 0.96, transition: { duration: 0.15 } }}
                >
                    <Icon className="mt-0.5 h-5 w-5 flex-shrink-0" aria-hidden="true" />
                    <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold">{message}</p>
                        {action && onAction && (
                            <button
                                onClick={() => {
                                    onAction();
                                    handleClose();
                                }}
                                className="mt-2 text-xs font-bold uppercase tracking-[0.18em] opacity-80 hover:opacity-100"
                            >
                                {actionLabel}
                            </button>
                        )}
                    </div>
                    <button
                        onClick={handleClose}
                        className="rounded-full p-1 transition-colors hover:bg-black/5"
                        aria-label={closeLabel}
                    >
                        <X className="h-4 w-4" aria-hidden="true" />
                    </button>
                </MotionDiv>
            )}
        </AnimatePresence>
    );
}
