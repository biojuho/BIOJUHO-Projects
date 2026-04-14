import PropTypes from 'prop-types';
import { ChevronRight, Sparkles } from 'lucide-react';
import { Badge } from '../ui/Badge';
import { scoreVariant } from '../../utils/vcScore';

export default function MatchCard({ t, match, onOpen }) {
    return (
        <button
            type="button"
            onClick={() => onOpen(match)}
            className="clay-panel-pressed flex h-full flex-col rounded-[1.8rem] p-5 text-left transition-all hover:-translate-y-1"
        >
            <div className="mb-4 flex items-start justify-between gap-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white text-primary shadow-clay-soft">
                    <Sparkles className="h-5 w-5" />
                </div>
                <Badge variant={scoreVariant(match.score)}>
                    {match.score}% {t('vcPortal.fitScore')}
                </Badge>
            </div>

            <h3 className="line-clamp-2 font-display text-2xl font-semibold text-ink">{match.title}</h3>
            <p className="mt-3 line-clamp-3 text-sm leading-7 text-ink-muted">{match.summary || t('vcPortal.noSummary')}</p>

            <div className="mt-4 rounded-[1.4rem] bg-white/60 p-4">
                <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.18em] text-ink-soft">{t('vcPortal.whyMatched')}</p>
                <p className="text-sm leading-7 text-ink-muted">{match.match_reason}</p>
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
                {(match.keywords || []).slice(0, 3).map((keyword) => (
                    <Badge key={keyword} variant="accent">{keyword}</Badge>
                ))}
            </div>

            <div className="mt-5 flex items-center justify-between border-t border-white/60 pt-4 text-sm">
                <span className="text-ink-soft">{t('vcPortal.source')}: BioLinker DB</span>
                <span className="inline-flex items-center gap-2 font-semibold text-primary">
                    {t('vcPortal.viewDetails')}
                    <ChevronRight className="h-4 w-4" />
                </span>
            </div>
        </button>
    );
}

MatchCard.propTypes = {
    t: PropTypes.func.isRequired,
    match: PropTypes.shape({
        score: PropTypes.number.isRequired,
        title: PropTypes.string.isRequired,
        summary: PropTypes.string,
        match_reason: PropTypes.string,
        keywords: PropTypes.arrayOf(PropTypes.string),
    }).isRequired,
    onOpen: PropTypes.func.isRequired,
};
