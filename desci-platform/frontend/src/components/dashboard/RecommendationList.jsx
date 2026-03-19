import { useState, useEffect } from 'react';
import { ExternalLink, Sparkles } from 'lucide-react';
import api from '../../services/api';
import { useLocale } from '../../contexts/LocaleContext';

export default function RecommendationList() {
    const [matches, setMatches] = useState([]);
    const [loading, setLoading] = useState(false);
    const { t } = useLocale();

    useEffect(() => {
        const fetchRecommendations = async () => {
            setLoading(true);
            try {
                const response = await api.get('/match/recommendations');
                setMatches(response.data);
            } catch (error) {
                console.error('Failed to load recommendations', error);
            } finally {
                setLoading(false);
            }
        };

        fetchRecommendations();
    }, []);

    if (loading) {
        return (
            <div className="clay-panel-pressed rounded-[1.6rem] p-6 text-center text-ink-muted">
                <Sparkles className="mx-auto mb-3 h-8 w-8 text-primary animate-pulseSoft" />
                <p>{t('recommendation.loading')}</p>
            </div>
        );
    }

    if (matches.length === 0) {
        return (
            <div className="clay-panel-pressed rounded-[1.6rem] p-6 text-center">
                <p className="font-semibold text-ink">{t('recommendation.emptyTitle')}</p>
                <p className="mt-2 text-sm text-ink-muted">{t('recommendation.emptyDescription')}</p>
            </div>
        );
    }

    return (
        <div className="space-y-3">
            {matches.map((match) => (
                <div key={match.id} className="clay-panel-pressed rounded-[1.6rem] p-5">
                    <div className="mb-3 flex items-center justify-between gap-3">
                        <span className="text-sm font-semibold text-ink">{match.title}</span>
                        <span className="rounded-full bg-primary/12 px-3 py-1 text-xs font-bold uppercase tracking-[0.18em] text-primary">
                            {match.score}% {t('recommendation.matchSuffix')}
                        </span>
                    </div>
                    <p className="mb-3 text-sm leading-7 text-ink-muted line-clamp-2">{match.summary}</p>
                    <div className="mb-4 flex items-center gap-2 text-sm text-primary">
                        <Sparkles className="h-4 w-4" />
                        <span>{match.match_reason}</span>
                    </div>
                    <a href={match.url || '#'} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 text-sm font-semibold text-ink hover:text-primary">
                        {t('recommendation.viewDetails')}
                        <ExternalLink className="h-4 w-4" />
                    </a>
                </div>
            ))}
        </div>
    );
}
