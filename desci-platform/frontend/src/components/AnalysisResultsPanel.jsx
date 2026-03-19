export default function AnalysisResultsPanel({
    fitScore,
    fitGrade,
    summary,
    strengths = [],
    weaknesses = [],
    gradeLabel,
    t,
}) {
    return (
        <div className="glass-card p-6">
            <div className="mb-5 flex items-center justify-between gap-4">
                <div>
                    <p className="clay-chip mb-3">{t('biolinker.analysisResult')}</p>
                    <h3 className="font-display text-5xl font-semibold text-ink">
                        {fitScore}
                        <span className="ml-2 text-xl text-ink-soft">{t('biolinker.scoreSuffix')}</span>
                    </h3>
                </div>
                <div className="clay-panel-pressed flex h-20 w-20 items-center justify-center rounded-full text-2xl font-bold text-primary">
                    {fitGrade}
                </div>
            </div>

            <p className="mb-5 text-sm font-semibold uppercase tracking-[0.18em] text-ink-soft">{gradeLabel} {t('biolinker.gradeSuffix')}</p>

            {summary && (
                <div className="clay-panel-pressed mb-5 rounded-[1.6rem] p-5 text-sm leading-7 text-ink-muted">
                    {summary}
                </div>
            )}

            <div className="grid gap-4 md:grid-cols-2">
                <div className="clay-panel-pressed rounded-[1.6rem] p-5">
                    <p className="mb-3 text-sm font-semibold text-ink">{t('biolinker.strengths')}</p>
                    <ul className="space-y-2 text-sm text-ink-muted">
                        {strengths.length ? strengths.map((item, index) => (
                            <li key={index}>• {item}</li>
                        )) : <li>• {t('common.noData')}</li>}
                    </ul>
                </div>
                <div className="clay-panel-pressed rounded-[1.6rem] p-5">
                    <p className="mb-3 text-sm font-semibold text-ink">{t('biolinker.weaknesses')}</p>
                    <ul className="space-y-2 text-sm text-ink-muted">
                        {weaknesses.length ? weaknesses.map((item, index) => (
                            <li key={index}>• {item}</li>
                        )) : <li>• {t('common.noData')}</li>}
                    </ul>
                </div>
            </div>
        </div>
    );
}
