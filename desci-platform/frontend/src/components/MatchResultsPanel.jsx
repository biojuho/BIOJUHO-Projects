/**
 * MatchResultsPanel - Papers list with scores and VC firms list
 * Props:
 *   papers   array of paper match objects
 *   vcs      array of VC firm objects
 *   loading  boolean
 *   t        translation function
 */
export default function MatchResultsPanel({ papers = [], vcs = [], loading, t }) {
    if (loading) {
        return (
            <div className="bg-white/[0.02] border border-white/[0.06] rounded-2xl p-10 text-center">
                <div className="inline-block animate-spin rounded-full h-10 w-10 border-2 border-white/10 border-t-primary mb-4" />
                <p className="text-white/30 text-sm">
                    {t('biolinker.matchLoading') ?? 'Finding matches…'}
                </p>
            </div>
        );
    }

    if (papers.length === 0 && vcs.length === 0) {
        return null;
    }

    return (
        <div className="space-y-6">
            {/* Papers section */}
            {papers.length > 0 && (
                <div
                    className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-6"
                    style={{ boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}
                >
                    <h3 className="font-display text-base font-semibold text-white mb-4">
                        {t('biolinker.paperMatches') ?? 'Paper Matches'}
                    </h3>
                    <div className="space-y-3">
                        {papers.map((paper, i) => (
                            <div
                                key={paper.id ?? i}
                                className="flex items-center justify-between gap-4 p-3 rounded-xl bg-white/[0.02] border border-white/[0.04]"
                            >
                                <div className="min-w-0 flex-1">
                                    <p className="text-sm font-medium text-white truncate">
                                        {paper.title ?? paper.id}
                                    </p>
                                    {paper.authors && (
                                        <p className="text-xs text-white/35 truncate mt-0.5">
                                            {Array.isArray(paper.authors)
                                                ? paper.authors.join(', ')
                                                : paper.authors}
                                        </p>
                                    )}
                                </div>
                                {paper.score != null && (
                                    <span className="shrink-0 text-xs font-bold text-primary bg-primary/10 border border-primary/20 px-2.5 py-1 rounded-lg">
                                        {Math.round(paper.score * 100)}%
                                    </span>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* VC firms section */}
            {vcs.length > 0 && (
                <div
                    className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-6"
                    style={{ boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}
                >
                    <h3 className="font-display text-base font-semibold text-white mb-4">
                        {t('biolinker.vcMatches') ?? 'VC Firms'}
                    </h3>
                    <div className="space-y-3">
                        {vcs.map((vc, i) => (
                            <div
                                key={vc.id ?? i}
                                className="flex items-center justify-between gap-4 p-3 rounded-xl bg-white/[0.02] border border-white/[0.04]"
                            >
                                <div className="min-w-0 flex-1">
                                    <p className="text-sm font-medium text-white truncate">
                                        {vc.name ?? vc.id}
                                    </p>
                                    {vc.focus && (
                                        <p className="text-xs text-white/35 truncate mt-0.5">
                                            {vc.focus}
                                        </p>
                                    )}
                                </div>
                                {vc.score != null && (
                                    <span className="shrink-0 text-xs font-bold text-accent-light bg-accent/10 border border-accent/20 px-2.5 py-1 rounded-lg">
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
