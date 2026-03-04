/**
 * BioLinker Dashboard Component
 */
import { lazy, Suspense, useState, useEffect, useCallback } from 'react';
import { useSearchParams, useLocation } from 'react-router-dom';
import client from '../services/api';
import MatchingResults from './MatchingResults';
import { useToast } from '../contexts/ToastContext';
import { useLocale } from '../contexts/LocaleContext';
import ReactMarkdown from 'react-markdown';

const ProposalView = lazy(() => import('./ProposalView'));

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

    const [uiState, setUiState] = useState({
        activeTab: 'rfp_analysis',
        loading: false,
        showProposal: false,
    });

    const [rfpState, setRfpState] = useState({
        text: '',
        profile: {
            company_name: '',
            tech_keywords: '',
            tech_description: '',
            company_size: '벤처기업',
            current_trl: 'TRL 4',
        },
        analysisResult: null,
    });

    const [matchState, setMatchState] = useState({
        matches: [],
        selectedRFP: null,
        proposalDraft: '',
        critiqueResult: '',
    });

    const [reviewState, setReviewState] = useState({
        topic: '',
        result: '',
        meta: null,
    });

    const updateUi = useCallback((updates) => setUiState((prev) => ({ ...prev, ...updates })), []);
    const updateRfp = useCallback((updates) => setRfpState((prev) => ({ ...prev, ...updates })), []);
    const updateMatch = useCallback((updates) => setMatchState((prev) => ({ ...prev, ...updates })), []);
    const updateReview = useCallback((updates) => setReviewState((prev) => ({ ...prev, ...updates })), []);

    const fetchMatches = useCallback(async (id) => {
        updateUi({ loading: true });
        try {
            const response = await client.post('/match/paper', { paper_id: id });
            updateMatch({ matches: response.data.matches });
        } catch (err) {
            showToast({ key: 'biolinker.matchingFailed' }, 'error');
            console.error(err);
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
    }, [location.state, updateUi, updateRfp, showToast]);

    useEffect(() => {
        if (paperId) {
            updateUi({ activeTab: 'paper_match' });
            fetchMatches(paperId);
        }
    }, [paperId, fetchMatches, updateUi]);

    const handleProfileChange = useCallback((field, value) => {
        setRfpState((prev) => ({
            ...prev,
            profile: { ...prev.profile, [field]: value },
        }));
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
    }, [rfpState.text, rfpState.profile, showToast, updateUi, updateRfp]);

    const handleGenerateProposal = useCallback(async (rfp) => {
        if (!paperId) {
            showToast({ key: 'biolinker.paperIdMissing' }, 'error');
            return;
        }

        updateUi({ loading: true });
        updateMatch({ selectedRFP: rfp });
        try {
            const response = await client.post('/proposal/generate', {
                paper_id: paperId,
                rfp_id: rfp.id,
            });
            updateMatch({
                proposalDraft: response.data.draft,
                critiqueResult: response.data.critique || '',
            });
            updateUi({ showProposal: true });
        } catch (err) {
            showToast({ key: 'biolinker.proposalFailed', values: { message: err.message } }, 'error');
        } finally {
            updateUi({ loading: false });
        }
    }, [paperId, showToast, updateUi, updateMatch]);

    const handleGenerateReview = useCallback(async () => {
        if (!reviewState.topic.trim()) {
            showToast({ key: 'biolinker.reviewTopicRequired' }, 'warning');
            return;
        }
        updateUi({ loading: true });
        updateReview({ result: '', meta: null });
        try {
            const response = await client.post('/api/agent/literature-review', {
                topic: reviewState.topic,
            });
            updateReview({ result: response.data.report, meta: response.data.meta || null });
            showToast({ key: 'biolinker.reviewComplete' }, 'success');
        } catch (err) {
            showToast({
                key: 'biolinker.reviewFailed',
                values: { message: err.response?.data?.detail || err.message },
            }, 'error');
        } finally {
            updateUi({ loading: false });
        }
    }, [reviewState.topic, showToast, updateUi, updateReview]);

    return (
        <div className="p-2 sm:p-6">
            <div className="max-w-7xl mx-auto">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-8 gap-4">
                    <div className="flex items-center gap-3">
                        <div className="p-2.5 rounded-xl" style={{ background: 'linear-gradient(135deg, rgba(0,212,170,0.12), rgba(99,102,241,0.12))' }}>
                            <span className="text-2xl">🧬</span>
                        </div>
                        <div>
                            <h1 className="font-display text-2xl sm:text-3xl font-bold text-white tracking-tight">{t('biolinker.headerTitle')}</h1>
                            <p className="text-white/30 text-sm">{t('biolinker.headerSubtitle')}</p>
                        </div>
                    </div>

                    <div className="flex bg-white/[0.03] p-1 rounded-xl border border-white/[0.06]">
                        {tabs.map((tab) => (
                            <button
                                key={tab.id}
                                onClick={() => updateUi({ activeTab: tab.id })}
                                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-300 ${
                                    uiState.activeTab === tab.id
                                        ? 'bg-primary/15 text-primary border border-primary/20'
                                        : 'text-white/35 hover:text-white/60 border border-transparent'
                                }`}
                            >
                                {tab.label}
                            </button>
                        ))}
                    </div>
                </div>

                {uiState.activeTab === 'literature_review' ? (
                    <div className="space-y-6 animate-fade-in">
                        <div className="bg-white/[0.03] backdrop-blur-xl border border-white/[0.06] rounded-2xl p-6" style={{ boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}>
                            <h2 className="font-display text-lg font-semibold text-white mb-3">{t('biolinker.reviewTitle')}</h2>
                            <p className="text-white/30 mb-5 text-sm leading-relaxed">{t('biolinker.reviewDescription')}</p>
                            <div className="flex gap-3">
                                <input
                                    className="glass-input flex-1"
                                    placeholder={t('biolinker.reviewPlaceholder')}
                                    value={reviewState.topic}
                                    onChange={(event) => updateReview({ topic: event.target.value })}
                                    onKeyDown={(event) => event.key === 'Enter' && handleGenerateReview()}
                                />
                                <button
                                    onClick={handleGenerateReview}
                                    disabled={uiState.loading}
                                    className="glass-button px-6 disabled:opacity-40 font-semibold"
                                >
                                    {uiState.loading ? t('biolinker.generatingReview') : t('biolinker.generateReview')}
                                </button>
                            </div>
                        </div>

                        {uiState.loading && !reviewState.result && (
                            <div className="bg-white/[0.02] border border-white/[0.06] rounded-2xl p-10 text-center">
                                <div className="inline-block animate-spin rounded-full h-10 w-10 border-2 border-white/10 border-t-primary mb-4"></div>
                                <h3 className="font-display text-base font-semibold text-white">{t('biolinker.reviewLoadingTitle')}</h3>
                                <p className="text-white/25 mt-2 text-sm">{t('biolinker.reviewLoadingBody')}</p>
                            </div>
                        )}

                        {reviewState.result && (
                            <div className="bg-surface/80 border border-white/[0.06] rounded-2xl p-8" style={{ boxShadow: '0 16px 48px rgba(0,0,0,0.5)' }}>
                                {reviewState.meta?.bridge_applied && (
                                    <div className="mb-4">
                                        <span className="text-[10px] uppercase tracking-[0.2em] px-2.5 py-1 rounded-full border border-primary/25 text-primary bg-primary/10">
                                            {t('common.bridgeApplied')}
                                        </span>
                                    </div>
                                )}
                                <div className="prose prose-invert max-w-none prose-headings:font-display prose-headings:text-white prose-p:text-white/70 prose-a:text-primary prose-strong:text-white">
                                    <ReactMarkdown>{reviewState.result}</ReactMarkdown>
                                </div>
                            </div>
                        )}
                    </div>
                ) : uiState.activeTab === 'paper_match' ? (
                    <div className="space-y-6 animate-fade-in">
                        {paperTitle && (
                            <div className="bg-primary/[0.06] border border-primary/15 p-4 rounded-xl text-white/60 mb-6 flex items-center gap-2">
                                <span className="text-primary">📄</span>
                                {t('biolinker.paperAnalyzing', { title: decodeURIComponent(paperTitle) })}
                            </div>
                        )}

                        <MatchingResults
                            matches={matchState.matches}
                            onSelect={handleGenerateProposal}
                            loading={uiState.loading && !matchState.proposalDraft}
                        />
                    </div>
                ) : (
                    <div className="grid lg:grid-cols-2 gap-6 animate-fade-in">
                        <div className="space-y-5">
                            <div className="bg-white/[0.03] backdrop-blur-xl border border-white/[0.06] rounded-2xl p-6" style={{ boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}>
                                <h2 className="font-display text-lg font-semibold text-white mb-4">{t('biolinker.companyProfile')}</h2>
                                <input
                                    className="glass-input w-full mb-3"
                                    placeholder={t('biolinker.companyName')}
                                    value={rfpState.profile.company_name}
                                    onChange={(event) => handleProfileChange('company_name', event.target.value)}
                                />
                                <input
                                    className="glass-input w-full"
                                    placeholder={t('biolinker.techKeywords')}
                                    value={rfpState.profile.tech_keywords}
                                    onChange={(event) => handleProfileChange('tech_keywords', event.target.value)}
                                />
                            </div>
                            <div className="bg-white/[0.03] backdrop-blur-xl border border-white/[0.06] rounded-2xl p-6" style={{ boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}>
                                <h2 className="font-display text-lg font-semibold text-white mb-4">{t('biolinker.rfpInput')}</h2>
                                <textarea
                                    className="glass-input w-full h-40 resize-none"
                                    placeholder={t('biolinker.rfpPlaceholder')}
                                    value={rfpState.text}
                                    onChange={(event) => updateRfp({ text: event.target.value })}
                                />
                                <button
                                    onClick={handleAnalyze}
                                    disabled={uiState.loading}
                                    className="glass-button mt-4 w-full py-3 font-semibold disabled:opacity-40"
                                >
                                    {uiState.loading ? t('biolinker.analyzing') : t('biolinker.analyze')}
                                </button>
                            </div>
                        </div>

                        <div className="space-y-6">
                            {rfpState.analysisResult && (
                                <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-6 text-white" style={{ boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}>
                                    <h3 className="font-display text-lg font-bold mb-4">
                                        {t('biolinker.analysisResult')}: <span className="text-primary">{rfpState.analysisResult.result.fit_grade}</span> {t('biolinker.gradeSuffix')}
                                    </h3>
                                    <p className="font-display text-4xl font-bold mb-2 text-gradient">{rfpState.analysisResult.result.fit_score}점</p>
                                    <p className="text-white/50">{gradeLabels[rfpState.analysisResult.result.fit_grade]}</p>
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {uiState.showProposal && matchState.selectedRFP && (
                    <Suspense
                        fallback={(
                            <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center">
                                <div className="animate-spin rounded-full h-14 w-14 border-2 border-white/10 border-t-primary"></div>
                            </div>
                        )}
                    >
                        <ProposalView
                            rfp={matchState.selectedRFP}
                            draft={matchState.proposalDraft}
                            critique={matchState.critiqueResult}
                            onClose={() => updateUi({ showProposal: false })}
                        />
                    </Suspense>
                )}

                {uiState.loading && uiState.showProposal && (
                    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center">
                        <div className="animate-spin rounded-full h-14 w-14 border-2 border-white/10 border-t-primary"></div>
                    </div>
                )}
            </div>
        </div>
    );
}
