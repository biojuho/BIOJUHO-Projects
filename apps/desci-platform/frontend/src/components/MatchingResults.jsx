import { useLocale } from '../contexts/LocaleContext';

const MatchingResults = ({ matches, onSelect, loading }) => {
    const { t } = useLocale();

    if (loading) {
        return (
            <div className="glass-card p-8 text-center">
                <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-4 border-white/70 border-t-primary" />
                <p className="text-sm text-ink-muted">{t('biolinker.matchLoading')}</p>
            </div>
        );
    }

    if (!matches || matches.length === 0) {
        return (
            <div className="glass-card p-8 text-center">
                <p className="text-sm text-ink-muted">{t('biolinker.noMatches')}</p>
            </div>
        );
    }

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <h2 className="font-display text-2xl font-semibold text-ink">{t('biolinker.matchesTitle')}</h2>
                <span className="rounded-full bg-primary/15 px-4 py-1 text-xs font-bold uppercase tracking-[0.18em] text-primary">
                    {t('biolinker.matchesCount', { count: matches.length })}
                </span>
            </div>
            <div className="grid gap-4">
                {matches.map((match) => (
                    <button
                        key={match.id}
                        type="button"
                        className="glass-card p-6 text-left transition-all hover:-translate-y-1"
                        onClick={() => onSelect(match)}
                    >
                        <div className="mb-3 flex items-center justify-between gap-4">
                            <span className="rounded-full bg-accent/12 px-3 py-1 text-xs font-bold uppercase tracking-[0.16em] text-accent-dark">
                                {match.metadata?.source}
                            </span>
                            <div className="text-sm text-ink-muted">
                                {t('biolinker.similarity')}{' '}
                                <span className="font-semibold text-primary">{(match.similarity * 100).toFixed(1)}%</span>
                            </div>
                        </div>
                        <h3 className="font-display text-xl font-semibold text-ink">{match.metadata?.title}</h3>
                        <p className="mt-3 line-clamp-2 text-sm leading-7 text-ink-muted">{match.document}</p>
                        <div className="mt-4 flex flex-wrap gap-2">
                            {(Array.isArray(match.metadata?.keywords) ? match.metadata.keywords : (match.metadata?.keywords || '').split(','))
                                .filter(Boolean)
                                .slice(0, 4)
                                .map((keyword, index) => (
                                    <span key={index} className="rounded-full bg-white/70 px-3 py-1 text-xs font-semibold text-ink-muted">
                                        #{keyword.trim()}
                                    </span>
                                ))}
                        </div>
                        <p className="mt-4 text-sm font-semibold text-primary">{t('biolinker.createProposal')}</p>
                    </button>
                ))}
            </div>
        </div>
    );
};

export default MatchingResults;
