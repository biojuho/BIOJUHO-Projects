import { lazy, Suspense, useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { useSearchParams, useLocation } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import client from '../services/api';
import MatchingResults from './MatchingResults';
import RFPInputPanel from './RFPInputPanel';
import AnalysisResultsPanel from './AnalysisResultsPanel';
import MatchResultsPanel from './MatchResultsPanel';
import { useToast } from '../contexts/ToastContext';
import { useLocale } from '../contexts/LocaleContext';
import { Badge } from './ui/Badge';
import { Button } from './ui/Button';

const ProposalView = lazy(() => import('./ProposalView'));
const MotionDiv = motion.div;

export default function BioLinker() {
    const [searchParams] = useSearchParams();
    const location = useLocation();
    const paperId = searchParams.get('paper_id');
    const paperTitle = searchParams.get('paper_title');
    const { showToast } = useToast();
    const { t } = useLocale();

    const tabs = [
        { id: 'rfp_analysis', label: t('biolinker.tabRfp') },
        { id: 'paper_match', label: t('biolinker.tabPaper') },
        { id: 'literature_review', label: t('biolinker.tabReview') },
    ];

    const gradeLabels = {
        S: t('biolinker.fitS'),
        A: t('biolinker.fitA'),
        B: t('biolinker.fitB'),
        C: t('biolinker.fitC'),
        D: t('biolinker.fitD'),
    };

    const [uiState, setUiState] = useState({ activeTab: 'rfp_analysis', loading: false, showProposal: false });
    const [rfpState, setRfpState] = useState({
        text: '',
        profile: {
            company_name: '',
            tech_keywords: '',
            tech_description: '',
            company_size: 'startup',
            current_trl: 'TRL 4',
        },
        analysisResult: null,
    });
    const [matchState, setMatchState] = useState({ matches: [], selectedRFP: null, proposalDraft: '', critiqueResult: '' });
    const [reviewState, setReviewState] = useState({ topic: '', result: '', meta: null });

    const updateUi = useCallback((updates) => setUiState((prev) => ({ ...prev, ...updates })), []);
    const updateRfp = useCallback((updates) => setRfpState((prev) => ({ ...prev, ...updates })), []);
    const updateMatch = useCallback((updates) => setMatchState((prev) => ({ ...prev, ...updates })), []);
    const updateReview = useCallback((updates) => setReviewState((prev) => ({ ...prev, ...updates })), []);

    const fetchMatches = useCallback(async (id) => {
        updateUi({ loading: true });
        try {
            const response = await client.post('/match/paper', { paper_id: id });
            updateMatch({ matches: response.data.matches || [] });
        } catch (err) {
            console.error(err);
            showToast({ key: 'biolinker.matchingFailed' }, 'error');
        } finally {
            updateUi({ loading: false });
        }
    }, [showToast, updateMatch, updateUi]);

    useEffect(() => {
        if (location.state?.from_notice) {
            updateUi({ activeTab: 'rfp_analysis' });
            if (location.state.rfp_text) updateRfp({ text: location.state.rfp_text });
            if (location.state.rfp_title) {
                showToast({ key: 'biolinker.noticeLoaded', values: { title: location.state.rfp_title } }, 'info');
            }
        }
    }, [location.state, showToast, updateRfp, updateUi]);

    useEffect(() => {
        if (paperId) {
            updateUi({ activeTab: 'paper_match' });
            fetchMatches(paperId);
        }
    }, [fetchMatches, paperId, updateUi]);

    const handleProfileChange = useCallback((field, value) => {
        setRfpState((prev) => ({ ...prev, profile: { ...prev.profile, [field]: value } }));
    }, []);

    const handleAnalyze = useCallback(async () => {
        if (!rfpState.text.trim() || !rfpState.profile.company_name) {
            showToast({ key: 'biolinker.inputRequired' }, 'warning');
            return;
        }

        updateUi({ loading: true });
        try {
            const response = await client.post('/analyze', {
                rfp_text: rfpState.text,
                user_profile: {
                    ...rfpState.profile,
                    tech_keywords: rfpState.profile.tech_keywords.split(',').map((keyword) => keyword.trim()),
                },
            });
            updateRfp({ analysisResult: response.data });
            showToast({ key: 'biolinker.analysisComplete' }, 'success');
        } catch {
            showToast({ key: 'biolinker.analysisFailed' }, 'error');
        } finally {
            updateUi({ loading: false });
        }
    }, [rfpState.profile, rfpState.text, showToast, updateRfp, updateUi]);

    const handleGenerateProposal = useCallback(async (rfp) => {
        if (!paperId) {
            showToast({ key: 'biolinker.paperIdMissing' }, 'error');
            return;
        }

        updateUi({ loading: true });
        updateMatch({ selectedRFP: rfp });
        try {
            const response = await client.post('/proposal/generate', { paper_id: paperId, rfp_id: rfp.id });
            updateMatch({ proposalDraft: response.data.draft, critiqueResult: response.data.critique || '' });
            updateUi({ showProposal: true });
        } catch (err) {
            showToast({ key: 'biolinker.proposalFailed', values: { message: err.message } }, 'error');
        } finally {
            updateUi({ loading: false });
        }
    }, [paperId, showToast, updateMatch, updateUi]);

    const handleGenerateReview = useCallback(async () => {
        if (!reviewState.topic.trim()) {
            showToast({ key: 'biolinker.reviewTopicRequired' }, 'warning');
            return;
        }

        updateUi({ loading: true });
        updateReview({ result: '', meta: null });
        try {
            const response = await client.post('/api/agent/literature-review', { topic: reviewState.topic });
            updateReview({ result: response.data.report, meta: response.data.meta || null });
            showToast({ key: 'biolinker.reviewComplete' }, 'success');
        } catch (err) {
            showToast({ key: 'biolinker.reviewFailed', values: { message: err.response?.data?.detail || err.message } }, 'error');
        } finally {
            updateUi({ loading: false });
        }
    }, [reviewState.topic, showToast, updateReview, updateUi]);

    const analysisPapers = rfpState.analysisResult?.result?.papers ?? [];
    const analysisVCs = rfpState.analysisResult?.result?.vcs ?? [];

    return (
        <div className="space-y-6">
            <GlassPanelHeader
                title={t('biolinker.headerTitle')}
                subtitle={t('biolinker.headerSubtitle')}
                tabs={tabs}
                activeTab={uiState.activeTab}
                onSelect={(id) => updateUi({ activeTab: id })}
            />

            {uiState.activeTab === 'literature_review' ? (
                <div className="space-y-6">
                    <div className="glass-card p-6">
                        <div className="mb-5">
                            <p className="clay-chip mb-3">{t('biolinker.reviewTitle')}</p>
                            <p className="text-sm leading-7 text-ink-muted">{t('biolinker.reviewDescription')}</p>
                        </div>
                        <div className="flex flex-col gap-3 sm:flex-row">
                            <input
                                className="clay-input flex-1"
                                placeholder={t('biolinker.reviewPlaceholder')}
                                value={reviewState.topic}
                                onChange={(event) => updateReview({ topic: event.target.value })}
                                onKeyDown={(event) => event.key === 'Enter' && handleGenerateReview()}
                            />
                            <Button onClick={handleGenerateReview} disabled={uiState.loading} className="justify-center text-white">
                                {uiState.loading ? t('biolinker.generatingReview') : t('biolinker.generateReview')}
                            </Button>
                        </div>
                    </div>

                    {uiState.loading && !reviewState.result && (
                        <div className="glass-card p-10 text-center">
                            <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-4 border-white/70 border-t-primary" />
                            <h3 className="font-display text-2xl font-semibold text-ink">{t('biolinker.reviewLoadingTitle')}</h3>
                            <p className="mt-3 text-sm text-ink-muted">{t('biolinker.reviewLoadingBody')}</p>
                        </div>
                    )}

                    {reviewState.result && (
                        <div className="glass-card p-8">
                            {reviewState.meta?.bridge_applied && (
                                <Badge variant="default" className="mb-4">{t('common.bridgeApplied')}</Badge>
                            )}
                            <div className="prose max-w-none prose-headings:font-display prose-headings:text-ink prose-p:text-ink-muted prose-a:text-primary prose-strong:text-ink">
                                <ReactMarkdown>{reviewState.result}</ReactMarkdown>
                            </div>
                        </div>
                    )}
                </div>
            ) : uiState.activeTab === 'paper_match' ? (
                <div className="space-y-5">
                    {paperTitle && (
                        <div className="glass-card flex items-center gap-3 p-4 text-sm text-ink-muted">
                            <Badge variant="accent">{t('biolinker.tabPaper')}</Badge>
                            <span>{t('biolinker.paperAnalyzing', { title: decodeURIComponent(paperTitle) })}</span>
                        </div>
                    )}
                    <MatchingResults matches={matchState.matches} onSelect={handleGenerateProposal} loading={uiState.loading && !matchState.proposalDraft} />
                </div>
            ) : (
                <div className="grid gap-6 xl:grid-cols-2">
                    <RFPInputPanel
                        profile={rfpState.profile}
                        onProfileChange={handleProfileChange}
                        rfpText={rfpState.text}
                        onRfpChange={(value) => updateRfp({ text: value })}
                        onAnalyze={handleAnalyze}
                        loading={uiState.loading}
                        t={t}
                    />
                    <div className="space-y-6">
                        {rfpState.analysisResult ? (
                            <>
                                <AnalysisResultsPanel
                                    fitScore={rfpState.analysisResult.result.fit_score}
                                    fitGrade={rfpState.analysisResult.result.fit_grade}
                                    summary={rfpState.analysisResult.result.summary}
                                    strengths={rfpState.analysisResult.result.strengths ?? []}
                                    weaknesses={rfpState.analysisResult.result.weaknesses ?? []}
                                    gradeLabel={gradeLabels[rfpState.analysisResult.result.fit_grade]}
                                    t={t}
                                />
                                <MatchResultsPanel papers={analysisPapers} vcs={analysisVCs} loading={false} t={t} />
                            </>
                        ) : (
                            <div className="glass-card p-8 text-center">
                                <p className="text-sm text-ink-muted">{t('biolinker.inputRequired')}</p>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {uiState.showProposal && matchState.selectedRFP && (
                <Suspense fallback={(
                    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#f2eadf]/70 backdrop-blur-md">
                        <div className="glass-card p-8">
                            <div className="h-12 w-12 animate-spin rounded-full border-4 border-white/70 border-t-primary" />
                        </div>
                    </div>
                )}>
                    <ProposalView
                        rfp={matchState.selectedRFP}
                        draft={matchState.proposalDraft}
                        critique={matchState.critiqueResult}
                        onClose={() => updateUi({ showProposal: false })}
                    />
                </Suspense>
            )}
        </div>
    );
}

function GlassPanelHeader({ title, subtitle, tabs, activeTab, onSelect }) {
    return (
        <MotionDiv initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-7">
            <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
                <div>
                    <p className="clay-chip mb-4">DSCI</p>
                    <h1 className="font-display text-4xl font-semibold text-ink">{title}</h1>
                    <p className="mt-3 max-w-3xl text-sm leading-7 text-ink-muted">{subtitle}</p>
                </div>
                <div className="clay-panel-pressed inline-flex rounded-full p-1">
                    {tabs.map((tab) => (
                        <button
                            key={tab.id}
                            type="button"
                            onClick={() => onSelect(tab.id)}
                            className={[
                                'rounded-full px-4 py-2 text-sm font-semibold transition-all',
                                activeTab === tab.id ? 'bg-white text-ink shadow-clay-soft' : 'text-ink-soft hover:text-ink',
                            ].join(' ')}
                        >
                            {tab.label}
                        </button>
                    ))}
                </div>
            </div>
        </MotionDiv>
    );
}
