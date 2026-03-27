import { ExternalLink, Mail, Phone } from 'lucide-react';
import { useLocale } from '../contexts/LocaleContext';

export default function Footer() {
    const { t } = useLocale();

    return (
        <footer className="mt-8 pb-4 pt-10">
            <div className="glass-card p-6">
                <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
                    <div>
                        <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-ink-soft">DSCI</p>
                        <p className="mt-2 max-w-xl text-sm leading-7 text-ink-muted">{t('footer.tagline')}</p>
                    </div>
                    <div className="space-y-2 text-sm text-ink-muted">
                        <p><span className="font-semibold text-ink">{t('footer.company')}:</span> Joolife</p>
                        <p>{t('footer.address')}</p>
                    </div>
                </div>
                <div className="soft-divider my-5" />
                <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                    <div className="flex flex-wrap items-center gap-4 text-sm text-ink-muted">
                        <a href="tel:010-3159-3708" className="inline-flex items-center gap-2 hover:text-ink">
                            <Phone className="h-4 w-4" />
                            010-3159-3708
                        </a>
                        <a href="mailto:joolife@joolife.io.kr" className="inline-flex items-center gap-2 hover:text-ink">
                            <Mail className="h-4 w-4" />
                            joolife@joolife.io.kr
                        </a>
                        <a href="https://joolife.io.kr" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 hover:text-ink">
                            <ExternalLink className="h-4 w-4" />
                            joolife.io.kr
                        </a>
                    </div>
                    <p className="text-xs text-ink-soft">&copy; {new Date().getFullYear()} Joolife. {t('footer.rights')}</p>
                </div>
            </div>
        </footer>
    );
}
