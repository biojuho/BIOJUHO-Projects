import PropTypes from 'prop-types';
import GlassCard from '../ui/GlassCard';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { scoreVariant } from '../../utils/vcScore';

export default function MatchDetailModal({ t, detail, onClose }) {
    if (!detail) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#e9dfd3]/70 p-4 backdrop-blur-sm" onClick={onClose}>
            <GlassCard className="w-full max-w-2xl p-0" onClick={(event) => event.stopPropagation()}>
                <div className="flex items-start justify-between gap-4 border-b border-white/60 px-6 py-5">
                    <div>
                        <Badge variant={scoreVariant(detail.score)}>{detail.score}% {t('vcPortal.fitScore')}</Badge>
                        <h2 className="mt-3 font-display text-3xl font-semibold text-ink">{detail.title}</h2>
                    </div>
                    <button type="button" onClick={onClose} className="clay-button h-11 w-11 !px-0">
                        X
                    </button>
                </div>

                <div className="space-y-5 px-6 py-6">
                    <div className="clay-panel-pressed rounded-[1.8rem] p-5">
                        <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.18em] text-ink-soft">{t('vcPortal.summary')}</p>
                        <p className="text-sm leading-7 text-ink-muted">{detail.summary || t('vcPortal.noSummary')}</p>
                    </div>

                    <div className="clay-panel-pressed rounded-[1.8rem] p-5">
                        <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.18em] text-ink-soft">{t('vcPortal.whyMatched')}</p>
                        <p className="text-sm leading-7 text-ink-muted">{detail.match_reason}</p>
                    </div>

                    {(detail.keywords || []).length > 0 && (
                        <div>
                            <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.18em] text-ink-soft">{t('vcPortal.keywords')}</p>
                            <div className="flex flex-wrap gap-2">
                                {detail.keywords.map((keyword) => (
                                    <Badge key={keyword} variant="outline">{keyword}</Badge>
                                ))}
                            </div>
                        </div>
                    )}

                    <div className="flex justify-end">
                        <Button onClick={onClose} className="justify-center text-white">
                            {t('common.close')}
                        </Button>
                    </div>
                </div>
            </GlassCard>
        </div>
    );
}

MatchDetailModal.propTypes = {
    t: PropTypes.func.isRequired,
    detail: PropTypes.shape({
        score: PropTypes.number.isRequired,
        title: PropTypes.string.isRequired,
        summary: PropTypes.string,
        match_reason: PropTypes.string,
        keywords: PropTypes.arrayOf(PropTypes.string),
    }),
    onClose: PropTypes.func.isRequired,
};
