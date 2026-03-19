import { Button } from './ui/Button';
import { Input } from './ui/Input';

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
            <div className="glass-card p-6">
                <p className="clay-chip mb-4">{t('biolinker.companyProfile')}</p>
                <div className="space-y-3">
                    <Input
                        placeholder={t('biolinker.companyName')}
                        value={profile.company_name}
                        onChange={(event) => onProfileChange('company_name', event.target.value)}
                    />
                    <Input
                        placeholder={t('biolinker.techKeywords')}
                        value={profile.tech_keywords}
                        onChange={(event) => onProfileChange('tech_keywords', event.target.value)}
                    />
                </div>
            </div>

            <div className="glass-card p-6">
                <p className="clay-chip mb-4">{t('biolinker.rfpInput')}</p>
                <textarea
                    className="clay-input min-h-[220px] resize-none"
                    placeholder={t('biolinker.rfpPlaceholder')}
                    value={rfpText}
                    onChange={(event) => onRfpChange(event.target.value)}
                />
                <Button onClick={onAnalyze} disabled={loading} className="mt-4 w-full justify-center text-white">
                    {loading ? t('biolinker.analyzing') : t('biolinker.analyze')}
                </Button>
            </div>
        </div>
    );
}
