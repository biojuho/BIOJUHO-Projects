import { Award, ChevronRight, FileCheck, Loader2, ShieldAlert } from 'lucide-react';
import { usePeerReview } from '../hooks/usePeerReview';
import { Badge } from './ui/Badge';
import { Button } from './ui/Button';

export default function PeerReview() {
    const {
        papers,
        isLoading,
        expandedPaperId,
        reviewText,
        rating,
        isSubmitting,
        togglePaper,
        setReviewText,
        setRating,
        submitReview,
        t,
    } = usePeerReview();

    if (isLoading) {
        return (
            <div className="glass-card flex min-h-[50vh] items-center justify-center p-8">
                <div className="text-center">
                    <Loader2 className="mx-auto mb-4 h-12 w-12 animate-spin text-primary" />
                    <p className="text-sm text-ink-muted">{t('peerReview.loading')}</p>
                </div>
            </div>
        );
    }

    const selectedPaper = papers.find((paper) => paper.id === expandedPaperId) || null;

    return (
        <div className="grid gap-6 xl:grid-cols-[340px,1fr]">
            <div className="space-y-4">
                <div className="glass-card p-6">
                    <p className="clay-chip mb-4">{t('layout.workspace')}</p>
                    <h1 className="font-display text-3xl font-semibold text-ink">{t('peerReview.title')}</h1>
                    <p className="mt-3 text-sm leading-7 text-ink-muted">{t('peerReview.subtitle')}</p>
                </div>

                <div className="space-y-3">
                    {papers.map((paper) => {
                        const active = expandedPaperId === paper.id;
                        return (
                            <button
                                key={paper.id}
                                type="button"
                                onClick={() => togglePaper(paper.id)}
                                className={[
                                    'glass-card w-full p-5 text-left transition-all',
                                    active ? 'ring-2 ring-primary/30' : '',
                                ].join(' ')}
                            >
                                <div className="mb-3 flex items-center justify-between">
                                    <Badge variant={paper.reward_claimed ? 'success' : 'default'}>
                                        {paper.reward_claimed ? t('peerReview.rewarded') : t('peerReview.ready')}
                                    </Badge>
                                    <ChevronRight className={`h-4 w-4 ${active ? 'text-primary' : 'text-ink-soft'}`} />
                                </div>
                                <h3 className="line-clamp-2 text-sm font-semibold text-ink">{paper.title}</h3>
                                <p className="mt-2 line-clamp-2 text-xs leading-6 text-ink-muted">{paper.abstract || t('common.noData')}</p>
                            </button>
                        );
                    })}
                </div>
            </div>

            {selectedPaper ? (
                <div className="glass-card p-8">
                    <div className="mb-6">
                        <h2 className="font-display text-3xl font-semibold text-ink">{selectedPaper.title}</h2>
                        <p className="mt-3 text-sm leading-7 text-ink-muted">{selectedPaper.abstract || t('common.noData')}</p>
                    </div>

                    <div className="grid gap-4 lg:grid-cols-[280px,1fr]">
                        <div className="clay-panel-pressed rounded-[1.8rem] p-5">
                            <p className="mb-4 text-sm font-semibold text-ink">{t('peerReview.scoreLabel')}</p>
                            <div className="mb-3 font-display text-5xl font-semibold text-primary">{rating}</div>
                            <input
                                type="range"
                                min="1"
                                max="10"
                                value={rating}
                                onChange={(event) => setRating(Number(event.target.value))}
                                className="w-full accent-[#46ad92]"
                            />
                            <div className="mt-3 flex justify-between text-xs text-ink-soft">
                                <span>{t('peerReview.scorePoor')}</span>
                                <span>{t('peerReview.scoreAverage')}</span>
                                <span>{t('peerReview.scoreExcellent')}</span>
                            </div>
                        </div>

                        <div className="space-y-4">
                            <div className="clay-panel-pressed rounded-[1.8rem] p-5">
                                <p className="mb-3 text-sm font-semibold text-ink">{t('peerReview.critiqueLabel')}</p>
                                <textarea
                                    value={reviewText}
                                    onChange={(event) => setReviewText(event.target.value)}
                                    className="clay-input min-h-[220px] resize-none"
                                    placeholder={t('peerReview.critiquePlaceholder')}
                                />
                            </div>

                            <div className="clay-panel-pressed flex items-start gap-3 rounded-[1.8rem] p-5">
                                <ShieldAlert className="mt-1 h-5 w-5 text-primary" />
                                <p className="text-sm leading-7 text-ink-muted">{t('peerReview.rewardCallout')}</p>
                            </div>
                        </div>
                    </div>

                    <div className="mt-6 flex justify-end">
                        <Button onClick={submitReview} disabled={isSubmitting} size="lg" className="justify-center text-white">
                            {isSubmitting ? <><Loader2 className="h-4 w-4 animate-spin" />{t('peerReview.submitting')}</> : <><Award className="h-4 w-4" />{t('peerReview.submit')}</>}
                        </Button>
                    </div>
                </div>
            ) : (
                <div className="glass-card flex min-h-[520px] items-center justify-center p-10 text-center">
                    <div>
                        <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-white text-primary shadow-clay-soft">
                            <FileCheck className="h-10 w-10" />
                        </div>
                        <h3 className="font-display text-3xl font-semibold text-ink">{t('peerReview.emptyTitle')}</h3>
                        <p className="mt-3 text-sm text-ink-muted">{t('peerReview.emptyDescription')}</p>
                    </div>
                </div>
            )}
        </div>
    );
}
