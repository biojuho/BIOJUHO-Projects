import { useEffect, useState } from 'react';
import { Building2, Globe, TrendingUp } from 'lucide-react';
import api from '../../services/api';
import { useLocale } from '../../contexts/LocaleContext';

export default function VCMatchList() {
    const [matches, setMatches] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const { t } = useLocale();

    useEffect(() => {
        const fetchMatches = async () => {
            try {
                const response = await api.get('/match/vc');
                setMatches(response.data);
            } catch (err) {
                console.error('VC Match Error:', err);
                setError(t('vcMatch.loadFailed'));
            } finally {
                setLoading(false);
            }
        };

        fetchMatches();
    }, [t]);

    if (loading) {
        return (
            <div className="clay-panel-pressed rounded-[1.6rem] p-6 text-center">
                <div className="mx-auto h-8 w-8 animate-spin rounded-full border-4 border-white/70 border-t-accent" />
            </div>
        );
    }

    if (error) {
        return <div className="clay-panel-pressed rounded-[1.6rem] p-4 text-sm text-error-dark">{error}</div>;
    }

    if (matches.length === 0) {
        return (
            <div className="clay-panel-pressed rounded-[1.6rem] p-6 text-center">
                <Building2 className="mx-auto mb-3 h-12 w-12 text-ink-soft opacity-40" />
                <p className="font-semibold text-ink">{t('vcMatch.emptyTitle')}</p>
                <p className="mt-2 text-sm text-ink-muted">{t('vcMatch.emptyDescription')}</p>
            </div>
        );
    }

    return (
        <div className="space-y-3">
            {matches.map((vc, index) => (
                <div key={vc.id || index} className="clay-panel-pressed rounded-[1.6rem] p-5">
                    <div className="mb-3 flex items-start justify-between gap-4">
                        <div>
                            <h4 className="text-lg font-semibold text-ink">{vc.name}</h4>
                            <div className="mt-2 flex items-center gap-2 text-xs uppercase tracking-[0.16em] text-ink-soft">
                                <Globe className="h-3 w-3" />
                                <span>{vc.country || t('vcMatch.global')}</span>
                            </div>
                        </div>
                        <div className="rounded-full bg-accent/15 px-3 py-1 text-xs font-bold uppercase tracking-[0.18em] text-accent-dark">
                            {vc.score} {t('vcMatch.matchLabel')}
                        </div>
                    </div>
                    <p className="mb-3 text-sm leading-7 text-ink-muted line-clamp-2">{vc.thesis_summary || vc.match_reason}</p>
                    <div className="flex items-center gap-2 text-sm text-primary">
                        <TrendingUp className="h-4 w-4" />
                        <span>{vc.match_reason}</span>
                    </div>
                </div>
            ))}
        </div>
    );
}
