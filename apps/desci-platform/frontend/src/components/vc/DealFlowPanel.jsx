import PropTypes from 'prop-types';
import { BarChart3, Sparkles } from 'lucide-react';
import GlassCard from '../ui/GlassCard';
import { Badge } from '../ui/Badge';

export default function DealFlowPanel({
    t,
    selectedVc,
    matches,
    isLoadingMatches,
    onOpenDetail,
    renderMatchCard,
}) {
    return (
        <GlassCard className="p-7">
            <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                    <h2 className="font-display text-3xl font-semibold text-ink">{t('vcPortal.dealFlowTitle')}</h2>
                    <p className="mt-2 text-sm leading-7 text-ink-muted">{t('vcPortal.dealFlowSubtitle')}</p>
                </div>
                {selectedVc && (
                    <Badge variant="outline">
                        <BarChart3 className="h-3 w-3" />
                        {selectedVc.name}
                    </Badge>
                )}
            </div>

            {isLoadingMatches ? (
                <div className="grid gap-4 md:grid-cols-2">
                    {[1, 2, 3, 4].map((index) => (
                        <div key={index} className="clay-panel-pressed h-56 rounded-[1.8rem] animate-pulse" />
                    ))}
                </div>
            ) : !selectedVc ? (
                <div className="clay-panel-pressed rounded-[1.8rem] p-8 text-center">
                    <Sparkles className="mx-auto mb-4 h-10 w-10 text-primary" />
                    <p className="font-semibold text-ink">{t('vcPortal.selectorPlaceholder')}</p>
                    <p className="mt-2 text-sm text-ink-muted">{t('vcPortal.selectorHint')}</p>
                </div>
            ) : matches.length === 0 ? (
                <div className="clay-panel-pressed rounded-[1.8rem] p-8 text-center">
                    <p className="font-semibold text-ink">{t('vcPortal.emptyTitle')}</p>
                    <p className="mt-2 text-sm text-ink-muted">{t('vcPortal.emptyDescription')}</p>
                </div>
            ) : (
                <div className="grid gap-4 md:grid-cols-2">
                    {matches.map((match) => renderMatchCard(match, onOpenDetail))}
                </div>
            )}
        </GlassCard>
    );
}

DealFlowPanel.propTypes = {
    t: PropTypes.func.isRequired,
    selectedVc: PropTypes.shape({
        name: PropTypes.string,
    }),
    matches: PropTypes.arrayOf(PropTypes.object).isRequired,
    isLoadingMatches: PropTypes.bool.isRequired,
    onOpenDetail: PropTypes.func.isRequired,
    renderMatchCard: PropTypes.func.isRequired,
};
