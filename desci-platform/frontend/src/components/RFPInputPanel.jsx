/**
 * RFPInputPanel - Company profile fields + RFP textarea + analyze button
 * Props:
 *   profile       { company_name, tech_keywords }
 *   onProfileChange(field, value)
 *   rfpText       string
 *   onRfpChange(value)
 *   onAnalyze()
 *   loading       boolean
 *   t             translation function
 */
export default function RFPInputPanel({
    profile,
    onProfileChange,
    rfpText,
    onRfpChange,
    onAnalyze,
    loading,
    t,
}) {
    return (
        <div className="space-y-5">
            {/* Company profile section */}
            <div
                className="bg-white/[0.03] backdrop-blur-xl border border-white/[0.06] rounded-2xl p-6"
                style={{ boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}
            >
                <h2 className="font-display text-lg font-semibold text-white mb-4">
                    {t('biolinker.companyProfile')}
                </h2>
                <input
                    className="glass-input w-full mb-3"
                    placeholder={t('biolinker.companyName')}
                    value={profile.company_name}
                    onChange={(event) => onProfileChange('company_name', event.target.value)}
                />
                <input
                    className="glass-input w-full"
                    placeholder={t('biolinker.techKeywords')}
                    value={profile.tech_keywords}
                    onChange={(event) => onProfileChange('tech_keywords', event.target.value)}
                />
            </div>

            {/* RFP text + analyze button section */}
            <div
                className="bg-white/[0.03] backdrop-blur-xl border border-white/[0.06] rounded-2xl p-6"
                style={{ boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}
            >
                <h2 className="font-display text-lg font-semibold text-white mb-4">
                    {t('biolinker.rfpInput')}
                </h2>
                <textarea
                    className="glass-input w-full h-40 resize-none"
                    placeholder={t('biolinker.rfpPlaceholder')}
                    value={rfpText}
                    onChange={(event) => onRfpChange(event.target.value)}
                />
                <button
                    onClick={onAnalyze}
                    disabled={loading}
                    className="glass-button mt-4 w-full py-3 font-semibold disabled:opacity-40"
                >
                    {loading ? t('biolinker.analyzing') : t('biolinker.analyze')}
                </button>
            </div>
        </div>
    );
}
