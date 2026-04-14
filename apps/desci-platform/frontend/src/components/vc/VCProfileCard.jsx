import PropTypes from 'prop-types';
import { BriefcaseBusiness, Globe2 } from 'lucide-react';
import GlassCard from '../ui/GlassCard';
import { Badge } from '../ui/Badge';

export default function VCProfileCard({ t, selectedVc }) {
    if (!selectedVc) {
        return (
            <GlassCard className="p-7">
                <div className="flex h-full min-h-[320px] flex-col items-center justify-center text-center">
                    <div className="mb-5 flex h-20 w-20 items-center justify-center rounded-full bg-white text-primary shadow-clay-soft">
                        <BriefcaseBusiness className="h-10 w-10" />
                    </div>
                    <h2 className="font-display text-3xl font-semibold text-ink">{t('vcPortal.selectorLabel')}</h2>
                    <p className="mt-3 max-w-md text-sm leading-7 text-ink-muted">{t('vcPortal.selectorHint')}</p>
                </div>
            </GlassCard>
        );
    }

    const preferredStages = selectedVc.preferred_stages ?? [];
    const focusAreas = selectedVc.portfolio_keywords ?? [];

    return (
        <GlassCard className="p-7">
            <div className="space-y-5">
                <div className="flex items-start justify-between gap-4">
                    <div>
                        <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-ink-soft">{t('vcPortal.title')}</p>
                        <h2 className="mt-2 font-display text-3xl font-semibold text-ink">{selectedVc.name}</h2>
                    </div>
                    <Badge variant="outline">
                        <Globe2 className="h-3 w-3" />
                        {selectedVc.country}
                    </Badge>
                </div>

                <div className="clay-panel-pressed rounded-[1.8rem] p-5">
                    <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.18em] text-ink-soft">{t('vcPortal.thesisTitle')}</p>
                    <p className="text-sm leading-7 text-ink-muted">{selectedVc.investment_thesis}</p>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                    <div className="clay-panel-pressed rounded-[1.8rem] p-5">
                        <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.18em] text-ink-soft">{t('vcPortal.preferredStages')}</p>
                        <div className="flex flex-wrap gap-2">
                            {preferredStages.map((stage) => (
                                <Badge key={stage} variant="default">{stage}</Badge>
                            ))}
                        </div>
                    </div>
                    <div className="clay-panel-pressed rounded-[1.8rem] p-5">
                        <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.18em] text-ink-soft">{t('vcPortal.focusAreas')}</p>
                        <div className="flex flex-wrap gap-2">
                            {focusAreas.map((keyword) => (
                                <Badge key={keyword} variant="accent">{keyword}</Badge>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </GlassCard>
    );
}

VCProfileCard.propTypes = {
    t: PropTypes.func.isRequired,
    selectedVc: PropTypes.shape({
        name: PropTypes.string,
        country: PropTypes.string,
        investment_thesis: PropTypes.string,
        preferred_stages: PropTypes.arrayOf(PropTypes.string),
        portfolio_keywords: PropTypes.arrayOf(PropTypes.string),
    }),
};
