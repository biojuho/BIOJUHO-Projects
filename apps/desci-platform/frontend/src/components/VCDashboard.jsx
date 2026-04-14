import { useLocale } from '../contexts/LocaleContext';
import { useVCDashboard } from '../hooks/useVCDashboard';
import VCSelectorCard from './vc/VCSelectorCard';
import VCProfileCard from './vc/VCProfileCard';
import DealFlowPanel from './vc/DealFlowPanel';
import MatchCard from './vc/MatchCard';
import MatchDetailModal from './vc/MatchDetailModal';

export default function VCDashboard() {
    const {
        vcList,
        selectedVc,
        matches,
        isLoadingMatches,
        activeDetail,
        selectVc,
        openDetail,
        closeDetail,
    } = useVCDashboard();
    const { t } = useLocale();

    const matchesCount = matches.length;

    return (
        <>
            <div className="space-y-6">
                <VCSelectorCard
                    t={t}
                    vcList={vcList}
                    selectedVc={selectedVc ? { ...selectedVc, matchesCount } : null}
                    onSelect={(vcId) => selectVc(vcList.find((vc) => vc.id === vcId) ?? null)}
                />

                <div className="grid gap-6 xl:grid-cols-[1.05fr,1.4fr]">
                    <VCProfileCard t={t} selectedVc={selectedVc} />

                    <DealFlowPanel
                        t={t}
                        selectedVc={selectedVc}
                        matches={matches}
                        isLoadingMatches={isLoadingMatches}
                        onOpenDetail={openDetail}
                        renderMatchCard={(match, onOpen) => (
                            <MatchCard key={match.asset_id} t={t} match={match} onOpen={onOpen} />
                        )}
                    />
                </div>
            </div>

            <MatchDetailModal t={t} detail={activeDetail} onClose={closeDetail} />
        </>
    );
}
