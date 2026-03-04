/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { formatMessage } from "../i18n/messages";

const DEFAULT_LOCALE = "ko-KR";
const DEFAULT_OUTPUT_LANGUAGE = "ko";
const LOCALE_STORAGE_KEY = "dsci.locale";
const OUTPUT_LANGUAGE_STORAGE_KEY = "dsci.outputLanguage";

const LocaleContext = createContext(null);

export function getStoredLocale() {
    if (typeof window === "undefined") {
        return DEFAULT_LOCALE;
    }
    return window.localStorage.getItem(LOCALE_STORAGE_KEY) || DEFAULT_LOCALE;
}

export function getStoredOutputLanguage() {
    if (typeof window === "undefined") {
        return DEFAULT_OUTPUT_LANGUAGE;
    }
    return window.localStorage.getItem(OUTPUT_LANGUAGE_STORAGE_KEY) || DEFAULT_OUTPUT_LANGUAGE;
}

export function LocaleProvider({ children }) {
    const [locale, setLocaleState] = useState(() => getStoredLocale());

    const outputLanguage = DEFAULT_OUTPUT_LANGUAGE;
    const setLocale = (nextLocale) => {
        const normalized = nextLocale === DEFAULT_LOCALE ? nextLocale : DEFAULT_LOCALE;
        setLocaleState(normalized);
    };

    useEffect(() => {
        if (typeof document !== "undefined") {
            document.documentElement.lang = locale;
        }
        if (typeof window !== "undefined") {
            window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
            window.localStorage.setItem(OUTPUT_LANGUAGE_STORAGE_KEY, outputLanguage);
        }
    }, [locale, outputLanguage]);

    const value = useMemo(
        () => ({
            locale,
            outputLanguage,
            setLocale,
            t: (key, values) => formatMessage(locale, key, values),
        }),
        [locale, outputLanguage],
    );

    return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale() {
    const context = useContext(LocaleContext);
    if (!context) {
        throw new Error("useLocale must be used within a LocaleProvider");
    }
    return context;
}
