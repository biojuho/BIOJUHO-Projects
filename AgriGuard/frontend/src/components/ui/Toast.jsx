import { useEffect, useCallback } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react';

const toastVariants = {
    initial: { opacity: 0, y: -20, scale: 0.95 },
    animate: { opacity: 1, y: 0, scale: 1 },
    exit: { opacity: 0, y: -20, scale: 0.95, transition: { duration: 0.15 } },
};

const icons = {
    success: CheckCircle,
    error: AlertCircle,
    warning: AlertTriangle,
    info: Info,
};

const styles = {
    success: {
        container: 'bg-emerald-50 border-emerald-200',
        icon: 'text-emerald-500',
        text: 'text-emerald-800',
    },
    error: {
        container: 'bg-red-50 border-red-200',
        icon: 'text-red-500',
        text: 'text-red-800',
    },
    warning: {
        container: 'bg-amber-50 border-amber-200',
        icon: 'text-amber-500',
        text: 'text-amber-800',
    },
    info: {
        container: 'bg-blue-50 border-blue-200',
        icon: 'text-blue-500',
        text: 'text-blue-800',
    },
};

export default function Toast({ message, type = 'info', onClose, duration = 4000 }) {
    const handleClose = useCallback(() => {
        onClose?.();
    }, [onClose]);

    useEffect(() => {
        if (duration && duration > 0 && message) {
            const timer = setTimeout(handleClose, duration);
            return () => clearTimeout(timer);
        }
    }, [duration, handleClose, message]);

    useEffect(() => {
        const handleKeyDown = (e) => {
            if (e.key === 'Escape') handleClose();
        };
        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, [handleClose]);

    const Icon = icons[type];
    const style = styles[type];

    return (
        <AnimatePresence>
            {message && (
                <motion.div
                    role="alert"
                    aria-live={type === 'error' ? 'assertive' : 'polite'}
                    className={`
                        fixed top-6 right-6 z-50
                        flex items-start gap-3 px-5 py-3.5
                        rounded-xl border shadow-lg
                        min-w-[280px] max-w-md
                        ${style.container}
                    `}
                    variants={toastVariants}
                    initial="initial"
                    animate="animate"
                    exit="exit"
                >
                    <Icon className={`w-5 h-5 flex-shrink-0 mt-0.5 ${style.icon}`} />
                    <p className={`flex-1 font-medium text-sm ${style.text}`}>{message}</p>
                    <button
                        onClick={handleClose}
                        className="p-1 -mr-1 hover:bg-black/5 rounded-lg transition-colors"
                        aria-label="닫기"
                    >
                        <X className="w-4 h-4 text-slate-400" />
                    </button>
                </motion.div>
            )}
        </AnimatePresence>
    );
}
