import { useLocale } from '../../contexts/LocaleContext';

export default function LocaleToggle({ className = '' }) {
  const { locale, setLocale, t } = useLocale();

  return (
    <div className={`clay-panel-pressed inline-flex items-center gap-1 rounded-full p-1 ${className}`.trim()}>
      {['ko-KR', 'en-US'].map((code) => {
        const active = locale === code;
        return (
          <button
            key={code}
            type="button"
            onClick={() => setLocale(code)}
            aria-label={t('locale.switchLabel')}
            className={[
              'rounded-full px-3 py-1.5 text-xs font-bold uppercase tracking-[0.18em] transition-all',
              active ? 'bg-white text-ink shadow-clay-soft' : 'text-ink-soft hover:text-ink',
            ].join(' ')}
          >
            {code === 'ko-KR' ? t('locale.shortKo') : t('locale.shortEn')}
          </button>
        );
      })}
    </div>
  );
}
