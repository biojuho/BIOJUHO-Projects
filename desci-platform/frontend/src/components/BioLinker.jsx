/**
 * BioLinker Dashboard Component
 * 정부 과제 적합도 분석 대시보드
 * Design: Bioluminescent Neural Network
 */
import { lazy, Suspense, useState, useEffect, useCallback } from 'react';
import { useSearchParams, useLocation } from 'react-router-dom';
import client from '../services/api';
import MatchingResults from './MatchingResults';
import { useToast } from '../contexts/ToastContext';
import ReactMarkdown from 'react-markdown';

const ProposalView = lazy(() => import('./ProposalView'));

const GRADE_LABELS = {
    S: '즉시 지원 추천 🔥',
    A: '높은 적합도 ✅',
    B: '전략적 판단 필요 ⚖️',
    C: '지원 비추천 ⚠️',
    D: '관련 없음 ❌',
};

const TABS = [
    { id: 'rfp_analysis', label: '공고 분석' },
    { id: 'paper_match', label: '논문 매칭' },
    { id: 'literature_review', label: '문헌 고찰 (AI)' },
];

export default function BioLinker() {
    const [searchParams] = useSearchParams();
    const location = useLocation();
    const paperId = searchParams.get('paper_id');
    const paperTitle = searchParams.get('paper_title');
    const { showToast } = useToast();

    // UI & Navigation State
    const [uiState, setUiState] = useState({
        activeTab: 'rfp_analysis',
        loading: false,
        showProposal: false
    });

    // RFP Analysis State
    const [rfpState, setRfpState] = useState({
        text: '',
        profile: {
            company_name: '',
            tech_keywords: '',
            tech_description: '',
            company_size: '벤처기업',
            current_trl: 'TRL 4',
        },
        analysisResult: null
    });

    // Paper Match State
    const [matchState, setMatchState] = useState({
        matches: [],
        selectedRFP: null,
        proposalDraft: '',
        critiqueResult: ''
    });

    // Literature Review State
    const [reviewState, setReviewState] = useState({
        topic: '',
        result: ''
    });

    const updateUi = useCallback((updates) => setUiState(prev => ({ ...prev, ...updates })), []);
    const updateRfp = useCallback((updates) => setRfpState(prev => ({ ...prev, ...updates })), []);
    const updateMatch = useCallback((updates) => setMatchState(prev => ({ ...prev, ...updates })), []);
    const updateReview = useCallback((updates) => setReviewState(prev => ({ ...prev, ...updates })), []);

    const fetchMatches = useCallback(async (id) => {
        updateUi({ loading: true });
        try {
            const response = await client.post('/match/paper', { paper_id: id });
            updateMatch({ matches: response.data.matches });
        } catch (err) {
            showToast('매칭 분석 중 오류가 발생했습니다.', 'error');
            console.error(err);
        } finally {
            updateUi({ loading: false });
        }
    }, [showToast, updateMatch, updateUi]);

    // Notices 페이지에서 공고 데이터를 state로 전달받은 경우
    useEffect(() => {
        if (location.state?.from_notice) {
            updateUi({ activeTab: 'rfp_analysis' });
            if (location.state.rfp_text) updateRfp({ text: location.state.rfp_text });
            if (location.state.rfp_title) {
                showToast(`'${location.state.rfp_title}' 공고가 로드됐습니다.`, 'info');
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
        setRfpState(prev => ({
            ...prev,
            profile: { ...prev.profile, [field]: value }
        }));
    }, []);

    const handleAnalyze = useCallback(async () => {
        if (!rfpState.text.trim() || !rfpState.profile.company_name) {
            showToast('공고문과 회사명을 입력해주세요.', 'warning');
            return;
        }
        updateUi({ loading: true });
        try {
            const response = await client.post('/analyze', {
                rfp_text: rfpState.text,
                user_profile: {
                    ...rfpState.profile,
                    tech_keywords: rfpState.profile.tech_keywords.split(',').map(k => k.trim())
                },
            });
            updateRfp({ analysisResult: response.data });
            showToast('분석이 완료되었습니다.', 'success');
        } catch {
            showToast('분석에 실패했습니다.', 'error');
        } finally {
            updateUi({ loading: false });
        }
    }, [rfpState.text, rfpState.profile, showToast, updateUi, updateRfp]);

    const handleGenerateProposal = useCallback(async (rfp) => {
        if (!paperId) {
            showToast("논문 ID가 없습니다.", 'error');
            return;
        }

        updateUi({ loading: true });
        updateMatch({ selectedRFP: rfp });
        try {
            const response = await client.post('/proposal/generate', {
                paper_id: paperId,
                rfp_id: rfp.id
            });
            updateMatch({
                proposalDraft: response.data.draft,
                critiqueResult: response.data.critique || ''
            });
            updateUi({ showProposal: true });
        } catch (err) {
            showToast('제안서 생성 실패: ' + err.message, 'error');
        } finally {
            updateUi({ loading: false });
        }
    }, [paperId, showToast, updateUi, updateMatch]);

    const handleGenerateReview = useCallback(async () => {
        if (!reviewState.topic.trim()) {
            showToast('연구 주제를 입력해주세요.', 'warning');
            return;
        }
        updateUi({ loading: true });
        updateReview({ result: '' });
        try {
            const response = await client.post('/api/agent/literature-review', {
                topic: reviewState.topic
            });
            updateReview({ result: response.data.report });
            showToast('문헌 고찰 생성 완료!', 'success');
        } catch (err) {
            showToast('문헌 고찰 생성 실패: ' + (err.response?.data?.detail || err.message), 'error');
        } finally {
            updateUi({ loading: false });
        }
    }, [reviewState.topic, showToast, updateUi, updateReview]);

    return (
        <div className="p-2 sm:p-6">
            <div className="max-w-7xl mx-auto">
                {/* Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-8 gap-4">
                    <div className="flex items-center gap-3">
                        <div className="p-2.5 rounded-xl" style={{ background: 'linear-gradient(135deg, rgba(0,212,170,0.12), rgba(99,102,241,0.12))' }}>
                            <span className="text-2xl">🧬</span>
                        </div>
                        <div>
                            <h1 className="font-display text-2xl sm:text-3xl font-bold text-white tracking-tight">BioLinker AI</h1>
                            <p className="text-white/30 text-sm">지능형 바이오 과제 매칭 & 제안서 생성</p>
                        </div>
                    </div>

                    <div className="flex bg-white/[0.03] p-1 rounded-xl border border-white/[0.06]">
                        {TABS.map(tab => (
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
                            <h2 className="font-display text-lg font-semibold text-white mb-3">💡 AI Literature Review 생성기</h2>
                            <p className="text-white/30 mb-5 text-sm leading-relaxed">관심 있는 연구 주제나 질병을 입력하면, 에이전트가 문헌을 검색해 종합적인 고찰(Review) 리포트를 작성합니다.</p>
                            <div className="flex gap-3">
                                <input
                                    className="glass-input flex-1"
                                    placeholder="예: CRISPR for Sickle Cell Disease"
                                    value={reviewState.topic}
                                    onChange={e => updateReview({ topic: e.target.value })}
                                    onKeyDown={(e) => e.key === 'Enter' && handleGenerateReview()}
                                />
                                <button
                                    onClick={handleGenerateReview}
                                    disabled={uiState.loading}
                                    className="glass-button px-6 disabled:opacity-40 font-semibold"
                                >
                                    {uiState.loading ? '검색 및 분석 중...' : '리뷰 생성'}
                                </button>
                            </div>
                        </div>

                        {uiState.loading && !reviewState.result && (
                            <div className="bg-white/[0.02] border border-white/[0.06] rounded-2xl p-10 text-center">
                                <div className="inline-block animate-spin rounded-full h-10 w-10 border-2 border-white/10 border-t-primary mb-4"></div>
                                <h3 className="font-display text-base font-semibold text-white">AI가 학술 문헌을 검색하고 종합 중입니다...</h3>
                                <p className="text-white/25 mt-2 text-sm">이 작업은 수집된 문헌 양에 따라 10~30초 정도 소요될 수 있습니다.</p>
                            </div>
                        )}

                        {reviewState.result && (
                            <div className="bg-surface/80 border border-white/[0.06] rounded-2xl p-8" style={{ boxShadow: '0 16px 48px rgba(0,0,0,0.5)' }}>
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
                                <span className="text-primary">📄</span> 분석 중인 논문: <span className="font-semibold text-white">{decodeURIComponent(paperTitle)}</span>
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
                        {/* RFP Analysis Input */}
                        <div className="space-y-5">
                            <div className="bg-white/[0.03] backdrop-blur-xl border border-white/[0.06] rounded-2xl p-6" style={{ boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}>
                                <h2 className="font-display text-lg font-semibold text-white mb-4">🏢 회사 프로필</h2>
                                <input
                                    className="glass-input w-full mb-3"
                                    placeholder="회사명"
                                    value={rfpState.profile.company_name}
                                    onChange={e => handleProfileChange('company_name', e.target.value)}
                                />
                                <input
                                    className="glass-input w-full"
                                    placeholder="보유 기술 (쉼표 구분)"
                                    value={rfpState.profile.tech_keywords}
                                    onChange={e => handleProfileChange('tech_keywords', e.target.value)}
                                />
                            </div>
                            <div className="bg-white/[0.03] backdrop-blur-xl border border-white/[0.06] rounded-2xl p-6" style={{ boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}>
                                <h2 className="font-display text-lg font-semibold text-white mb-4">📄 공고문 입력</h2>
                                <textarea
                                    className="glass-input w-full h-40 resize-none"
                                    placeholder="공고문 텍스트 붙여넣기..."
                                    value={rfpState.text}
                                    onChange={e => updateRfp({ text: e.target.value })}
                                />
                                <button
                                    onClick={handleAnalyze}
                                    disabled={uiState.loading}
                                    className="glass-button mt-4 w-full py-3 font-semibold disabled:opacity-40"
                                >
                                    {uiState.loading ? '분석 중...' : '적합도 분석'}
                                </button>
                            </div>
                        </div>

                        {/* Analysis Result */}
                        <div className="space-y-6">
                            {rfpState.analysisResult && (
                                <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-6 text-white" style={{ boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}>
                                    <h3 className="font-display text-lg font-bold mb-4">분석 결과: <span className="text-primary">{rfpState.analysisResult.result.fit_grade}</span> 등급</h3>
                                    <p className="font-display text-4xl font-bold mb-2 text-gradient">{rfpState.analysisResult.result.fit_score}점</p>
                                    <p className="text-white/50">{GRADE_LABELS[rfpState.analysisResult.result.fit_grade]}</p>
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* Proposal Modal */}
                {uiState.showProposal && matchState.selectedRFP && (
                    <Suspense
                        fallback={
                            <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center">
                                <div className="animate-spin rounded-full h-14 w-14 border-2 border-white/10 border-t-primary"></div>
                            </div>
                        }
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
