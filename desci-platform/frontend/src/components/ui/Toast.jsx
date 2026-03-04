import { useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react';

const MotionDiv = motion.div;

const toastVariants = {
    initial: { opacity: 0, y: -20, scale: 0.95 },
    animate: { opacity: 1, y: 0, scale: 1 },
    exit: { opacity: 0, y: -20, scale: 0.95, transition: { duration: 0.15 } }
};

const icons = {
    success: CheckCircle,
    error: AlertCircle,
    warning: AlertTriangle,
    info: Info
};

const styles = {
    success: {
        container: 'bg-success/10 border-success/30',
        icon: 'text-success-light',
        text: 'text-success-light',
    },
    error: {
        container: 'bg-error/10 border-error/30',
        icon: 'text-error-light',
        text: 'text-error-light',
    },
    warning: {
        container: 'bg-warning/10 border-warning/30',
        icon: 'text-warning-light',
        text: 'text-warning-light',
    },
    info: {
        container: 'bg-info/10 border-info/30',
        icon: 'text-info-light',
        text: 'text-info-light',
    }
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
        if (duration && duration > 0) {
            const timer = setTimeout(handleClose, duration);
            return () => clearTimeout(timer);
        }
    }, [duration, handleClose]);

    // Close on escape key
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (e.key === 'Escape') {
                handleClose();
            }
        };
        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, [handleClose]);

    const Icon = icons[type];
    const style = styles[type];

    return (
        <AnimatePresence>
            {message && (
                <MotionDiv
                    role="alert"
                    aria-live={type === 'error' ? 'assertive' : 'polite'}
                    aria-atomic="true"
                    className={`
                        fixed top-20 right-4 md:right-8 z-50
                        flex items-start gap-3 px-4 py-3 md:px-6 md:py-4
                        rounded-xl border backdrop-blur-md shadow-2xl
                        min-w-[280px] max-w-[90vw] md:max-w-md
                        ${style.container}
                    `}
                    variants={toastVariants}
                    initial="initial"
                    animate="animate"
                    exit="exit"
                >
                    {/* Icon */}
                    <Icon
                        className={`w-5 h-5 flex-shrink-0 mt-0.5 ${style.icon}`}
                        aria-hidden="true"
                    />

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                        <p className={`font-medium text-sm ${style.text}`}>
                            {message}
                        </p>

                        {/* Action button */}
                        {action && onAction && (
                            <button
                                onClick={() => {
                                    onAction();
                                    handleClose();
                                }}
                                className={`mt-2 text-sm font-semibold underline underline-offset-2 hover:opacity-80 transition-opacity ${style.text}`}
                            >
                                {actionLabel}
                            </button>
                        )}
                    </div>

                    {/* Close button */}
                    <button
                        onClick={handleClose}
                        className="p-1.5 -mr-1 hover:bg-white/10 rounded-lg transition-colors flex-shrink-0"
                        aria-label={closeLabel}
                    >
                        <X className="w-4 h-4 text-white/70" aria-hidden="true" />
                    </button>
                </MotionDiv>
            )}
        </AnimatePresence>
    );
}
