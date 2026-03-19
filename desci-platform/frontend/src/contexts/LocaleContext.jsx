/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { formatMessage } from '../i18n/messages';

export const SUPPORTED_LOCALES = ['ko-KR', 'en-US'];
const DEFAULT_LOCALE = 'ko-KR';
const LOCALE_STORAGE_KEY = 'dsci.locale';
const OUTPUT_LANGUAGE_STORAGE_KEY = 'dsci.outputLanguage';

const LocaleContext = createContext(null);

function normalizeLocale(nextLocale) {
    return SUPPORTED_LOCALES.includes(nextLocale) ? nextLocale : DEFAULT_LOCALE;
}

function localeToOutputLanguage(locale) {
    return locale === 'en-US' ? 'en' : 'ko';
}

export function getStoredLocale() {
    if (typeof window === 'undefined') {
        return DEFAULT_LOCALE;
    }

    return normalizeLocale(window.localStorage.getItem(LOCALE_STORAGE_KEY));
}

export function getStoredOutputLanguage() {
    return localeToOutputLanguage(getStoredLocale());
}

export function LocaleProvider({ children }) {
    const [locale, setLocaleState] = useState(() => getStoredLocale());

    const setLocale = (nextLocale) => {
        setLocaleState(normalizeLocale(nextLocale));
    };

    const toggleLocale = () => {
        setLocaleState((current) => (current === 'ko-KR' ? 'en-US' : 'ko-KR'));
    };

    useEffect(() => {
        const outputLanguage = localeToOutputLanguage(locale);

        if (typeof document !== 'undefined') {
            document.documentElement.lang = locale;
        }

        if (typeof window !== 'undefined') {
            window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
            window.localStorage.setItem(OUTPUT_LANGUAGE_STORAGE_KEY, outputLanguage);
        }
    }, [locale]);

    const value = useMemo(() => {
        const outputLanguage = localeToOutputLanguage(locale);

        return {
            locale,
            outputLanguage,
            setLocale,
            toggleLocale,
            t: (key, values) => formatMessage(locale, key, values),
        };
    }, [locale]);

    return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale() {
    const context = useContext(LocaleContext);

    if (!context) {
        throw new Error('useLocale must be used within a LocaleProvider');
    }

    return context;
}
