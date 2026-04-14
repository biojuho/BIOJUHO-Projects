import PropTypes from 'prop-types';
import { Search } from 'lucide-react';
import GlassCard from '../ui/GlassCard';

export default function VCSelectorCard({ t, vcList, selectedVc, onSelect }) {
    return (
        <GlassCard className="overflow-hidden p-8">
            <div className="grid gap-6 lg:grid-cols-[1.45fr,1fr]">
                <div>
                    <p className="clay-chip mb-4">{t('layout.market')}</p>
                    <h1 className="font-display text-4xl font-semibold text-ink sm:text-5xl">{t('vcPortal.title')}</h1>
                    <p className="mt-4 max-w-2xl text-sm leading-8 text-ink-muted">{t('vcPortal.subtitle')}</p>

                    <div className="mt-6 grid gap-4 sm:grid-cols-3">
                        <div className="clay-panel-pressed rounded-[1.7rem] p-5">
                            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-ink-soft">{t('vcPortal.selectorLabel')}</p>
                            <p className="mt-2 font-display text-3xl font-semibold text-ink">{vcList.length}</p>
                        </div>
                        <div className="clay-panel-pressed rounded-[1.7rem] p-5">
                            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-ink-soft">{t('vcPortal.preferredStages')}</p>
                            <p className="mt-2 font-display text-3xl font-semibold text-ink">{selectedVc?.preferred_stages?.length ?? 0}</p>
                        </div>
                        <div className="clay-panel-pressed rounded-[1.7rem] p-5">
                            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-ink-soft">{t('vcPortal.dealFlowTitle')}</p>
                            <p className="mt-2 font-display text-3xl font-semibold text-ink">{selectedVc?.matchesCount ?? 0}</p>
                        </div>
                    </div>
                </div>

                <div className="clay-panel-pressed rounded-[2rem] p-6">
                    <div className="mb-4 flex items-center gap-3">
                        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white text-primary shadow-clay-soft">
                            <Search className="h-5 w-5" />
                        </div>
                        <div>
                            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-ink-soft">{t('vcPortal.selectorLabel')}</p>
                            <p className="text-sm text-ink-muted">{t('vcPortal.selectorHint')}</p>
                        </div>
                    </div>
                    <label className="mb-2 block text-sm font-semibold text-ink">{t('vcPortal.selectorLabel')}</label>
                    <select
                        className="clay-input w-full"
                        onChange={(event) => onSelect(event.target.value)}
                        value={selectedVc?.id || ''}
                    >
                        <option value="">{t('vcPortal.selectorPlaceholder')}</option>
                        {vcList.map((vc) => (
                            <option key={vc.id} value={vc.id}>
                                {vc.name} ({vc.country})
                            </option>
                        ))}
                    </select>
                </div>
            </div>
        </GlassCard>
    );
}

VCSelectorCard.propTypes = {
    t: PropTypes.func.isRequired,
    vcList: PropTypes.arrayOf(PropTypes.shape({
        id: PropTypes.string,
        name: PropTypes.string,
        country: PropTypes.string,
    })).isRequired,
    selectedVc: PropTypes.shape({
        id: PropTypes.string,
        preferred_stages: PropTypes.arrayOf(PropTypes.string),
        matchesCount: PropTypes.number,
    }),
    onSelect: PropTypes.func.isRequired,
};
