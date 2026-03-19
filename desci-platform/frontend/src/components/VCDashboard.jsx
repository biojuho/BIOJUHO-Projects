import { BarChart3, BriefcaseBusiness, ChevronRight, Globe2, Search, Sparkles, X } from 'lucide-react';
import { useLocale } from '../contexts/LocaleContext';
import { useVCDashboard } from '../hooks/useVCDashboard';
import GlassCard from './ui/GlassCard';
import { Badge } from './ui/Badge';
import { Button } from './ui/Button';

function scoreVariant(score) {
    if (score >= 90) return 'success';
    if (score >= 80) return 'info';
    if (score >= 70) return 'warning';
    return 'secondary';
}

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

    const preferredStages = selectedVc?.preferred_stages ?? [];
    const focusAreas = selectedVc?.portfolio_keywords ?? [];

    return (
        <>
            <div className="space-y-6">
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
                                    <p className="mt-2 font-display text-3xl font-semibold text-ink">{preferredStages.length}</p>
                                </div>
                                <div className="clay-panel-pressed rounded-[1.7rem] p-5">
                                    <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-ink-soft">{t('vcPortal.dealFlowTitle')}</p>
                                    <p className="mt-2 font-display text-3xl font-semibold text-ink">{matches.length}</p>
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
                                onChange={(event) => selectVc(vcList.find((vc) => vc.id === event.target.value) ?? null)}
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

                <div className="grid gap-6 xl:grid-cols-[1.05fr,1.4fr]">
                    <GlassCard className="p-7">
                        {selectedVc ? (
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
                        ) : (
                            <div className="flex h-full min-h-[320px] flex-col items-center justify-center text-center">
                                <div className="mb-5 flex h-20 w-20 items-center justify-center rounded-full bg-white text-primary shadow-clay-soft">
                                    <BriefcaseBusiness className="h-10 w-10" />
                                </div>
                                <h2 className="font-display text-3xl font-semibold text-ink">{t('vcPortal.selectorLabel')}</h2>
                                <p className="mt-3 max-w-md text-sm leading-7 text-ink-muted">{t('vcPortal.selectorHint')}</p>
                            </div>
                        )}
                    </GlassCard>

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
                                {matches.map((match) => (
                                    <button
                                        key={match.asset_id}
                                        type="button"
                                        onClick={() => openDetail(match)}
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
                                ))}
                            </div>
                        )}
                    </GlassCard>
                </div>
            </div>

            {activeDetail && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#e9dfd3]/70 p-4 backdrop-blur-sm" onClick={closeDetail}>
                    <GlassCard className="w-full max-w-2xl p-0" onClick={(event) => event.stopPropagation()}>
                        <div className="flex items-start justify-between gap-4 border-b border-white/60 px-6 py-5">
                            <div>
                                <Badge variant={scoreVariant(activeDetail.score)}>{activeDetail.score}% {t('vcPortal.fitScore')}</Badge>
                                <h2 className="mt-3 font-display text-3xl font-semibold text-ink">{activeDetail.title}</h2>
                            </div>
                            <button type="button" onClick={closeDetail} className="clay-button h-11 w-11 !px-0">
                                <X className="h-4 w-4" />
                            </button>
                        </div>

                        <div className="space-y-5 px-6 py-6">
                            <div className="clay-panel-pressed rounded-[1.8rem] p-5">
                                <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.18em] text-ink-soft">{t('vcPortal.summary')}</p>
                                <p className="text-sm leading-7 text-ink-muted">{activeDetail.summary || t('vcPortal.noSummary')}</p>
                            </div>

                            <div className="clay-panel-pressed rounded-[1.8rem] p-5">
                                <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.18em] text-ink-soft">{t('vcPortal.whyMatched')}</p>
                                <p className="text-sm leading-7 text-ink-muted">{activeDetail.match_reason}</p>
                            </div>

                            {(activeDetail.keywords || []).length > 0 && (
                                <div>
                                    <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.18em] text-ink-soft">{t('vcPortal.keywords')}</p>
                                    <div className="flex flex-wrap gap-2">
                                        {activeDetail.keywords.map((keyword) => (
                                            <Badge key={keyword} variant="outline">{keyword}</Badge>
                                        ))}
                                    </div>
                                </div>
                            )}

                            <div className="flex justify-end">
                                <Button onClick={closeDetail} className="justify-center text-white">
                                    {t('common.close')}
                                </Button>
                            </div>
                        </div>
                    </GlassCard>
                </div>
            )}
        </>
    );
}
