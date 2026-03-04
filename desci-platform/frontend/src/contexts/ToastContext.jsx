/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useCallback } from 'react';
import Toast from '../components/ui/Toast';
import { useLocale } from './LocaleContext';

const ToastContext = createContext(null);

export function ToastProvider({ children }) {
    const { t } = useLocale();
    const [toast, setToast] = useState(null);

    const showToast = useCallback((message, type = 'info') => {
        if (typeof message === 'string') {
            setToast({ message, type });
            return;
        }
        if (message?.key) {
            setToast({
                message: t(message.key, message.values),
                type,
            });
            return;
        }
        setToast({ message: message?.fallback || '', type });
    }, [t]);

    const hideToast = useCallback(() => {
        setToast(null);
    }, []);

    return (
        <ToastContext.Provider value={{ showToast, hideToast }}>
            {children}
            <Toast
                message={toast?.message}
                type={toast?.type}
                onClose={hideToast}
                closeLabel={t('toast.dismiss')}
            />
        </ToastContext.Provider>
    );
}

export function useToast() {
    const context = useContext(ToastContext);
    if (!context) {
        throw new Error('useToast must be used within a ToastProvider');
    }
    return context;
}
