export default function MatchResultsPanel({ papers = [], vcs = [], loading, t }) {
    if (loading) {
        return (
            <div className="glass-card p-8 text-center">
                <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-4 border-white/70 border-t-primary" />
                <p className="text-sm text-ink-muted">{t('biolinker.matchLoading')}</p>
            </div>
        );
    }

    if (papers.length === 0 && vcs.length === 0) {
        return null;
    }

    return (
        <div className="space-y-5">
            {papers.length > 0 && (
                <div className="glass-card p-6">
                    <p className="clay-chip mb-4">{t('biolinker.paperMatches')}</p>
                    <div className="space-y-3">
                        {papers.map((paper, index) => (
                            <div key={paper.id ?? index} className="clay-panel-pressed flex items-center justify-between gap-4 rounded-[1.5rem] p-4">
                                <div className="min-w-0">
                                    <p className="truncate text-sm font-semibold text-ink">{paper.title ?? paper.id}</p>
                                    {paper.authors && (
                                        <p className="mt-1 text-xs text-ink-muted truncate">
                                            {Array.isArray(paper.authors) ? paper.authors.join(', ') : paper.authors}
                                        </p>
                                    )}
                                </div>
                                {paper.score != null && (
                                    <span className="rounded-full bg-primary/15 px-3 py-1 text-xs font-bold uppercase tracking-[0.16em] text-primary">
                                        {Math.round(paper.score * 100)}%
                                    </span>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {vcs.length > 0 && (
                <div className="glass-card p-6">
                    <p className="clay-chip mb-4">{t('biolinker.vcMatches')}</p>
                    <div className="space-y-3">
                        {vcs.map((vc, index) => (
                            <div key={vc.id ?? index} className="clay-panel-pressed flex items-center justify-between gap-4 rounded-[1.5rem] p-4">
                                <div className="min-w-0">
                                    <p className="truncate text-sm font-semibold text-ink">{vc.name ?? vc.id}</p>
                                    {vc.focus && <p className="mt-1 truncate text-xs text-ink-muted">{vc.focus}</p>}
                                </div>
                                {vc.score != null && (
                                    <span className="rounded-full bg-accent/15 px-3 py-1 text-xs font-bold uppercase tracking-[0.16em] text-accent-dark">
                                        {Math.round(vc.score * 100)}%
                                    </span>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
