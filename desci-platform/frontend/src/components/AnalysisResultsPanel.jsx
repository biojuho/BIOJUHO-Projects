/**
 * AnalysisResultsPanel - Displays fit score, grade, strengths and weaknesses
 * Props:
 *   fitScore    number
 *   fitGrade    string  ('S' | 'A' | 'B' | 'C' | 'D')
 *   summary     string  (optional)
 *   strengths   string[] (optional)
 *   weaknesses  string[] (optional)
 *   gradeLabel  string  localised grade description
 *   t           translation function
 */
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
        <div
            className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-6 text-white space-y-5"
            style={{ boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}
        >
            {/* Score + grade header */}
            <div>
                <h3 className="font-display text-lg font-bold mb-4">
                    {t('biolinker.analysisResult')}:{' '}
                    <span className="text-primary">{fitGrade}</span>{' '}
                    {t('biolinker.gradeSuffix')}
                </h3>
                <p className="font-display text-4xl font-bold mb-2 text-gradient">
                    {fitScore}{t('biolinker.scoreSuffix') ?? '점'}
                </p>
                {gradeLabel && (
                    <p className="text-white/50">{gradeLabel}</p>
                )}
            </div>

            {/* Summary */}
            {summary && (
                <p className="text-white/60 text-sm leading-relaxed border-t border-white/[0.06] pt-4">
                    {summary}
                </p>
            )}

            {/* Strengths */}
            {strengths.length > 0 && (
                <div className="border-t border-white/[0.06] pt-4">
                    <h4 className="text-sm font-semibold text-primary mb-2">
                        {t('biolinker.strengths') ?? 'Strengths'}
                    </h4>
                    <ul className="space-y-1">
                        {strengths.map((item, i) => (
                            <li key={i} className="text-white/60 text-sm flex items-start gap-2">
                                <span className="text-primary mt-0.5">+</span>
                                <span>{item}</span>
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {/* Weaknesses */}
            {weaknesses.length > 0 && (
                <div className="border-t border-white/[0.06] pt-4">
                    <h4 className="text-sm font-semibold text-white/40 mb-2">
                        {t('biolinker.weaknesses') ?? 'Weaknesses'}
                    </h4>
                    <ul className="space-y-1">
                        {weaknesses.map((item, i) => (
                            <li key={i} className="text-white/50 text-sm flex items-start gap-2">
                                <span className="text-white/30 mt-0.5">-</span>
                                <span>{item}</span>
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
}
