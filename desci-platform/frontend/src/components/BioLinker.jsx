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

// eslint-disable-next-line no-unused-vars
const gradeColors = {
    S: 'bg-gradient-to-r from-highlight to-highlight-dark',
    A: 'bg-gradient-to-r from-primary to-primary-600',
    B: 'bg-gradient-to-r from-accent-light to-accent',
    C: 'bg-gradient-to-r from-secondary to-gray-500',
    D: 'bg-gradient-to-r from-error-light to-error',
};

const gradeLabels = {
    S: '즉시 지원 추천 🔥',
    A: '높은 적합도 ✅',
    B: '전략적 판단 필요 ⚖️',
    C: '지원 비추천 ⚠️',
    D: '관련 없음 ❌',
};

export default function BioLinker() {
    const [searchParams] = useSearchParams();
    const location = useLocation();
    const paperId = searchParams.get('paper_id');
    const paperTitle = searchParams.get('paper_title');
    const { showToast } = useToast();

    const [activeTab, setActiveTab] = useState('rfp_analysis');

    // RFP Analysis State
    const [rfpText, setRfpText] = useState('');
    const [profile, setProfile] = useState({
        company_name: '',
        tech_keywords: '',
        tech_description: '',
        company_size: '벤처기업',
        current_trl: 'TRL 4',
    });
    const [analysisResult, setAnalysisResult] = useState(null);

    // Paper Match State
    const [matches, setMatches] = useState([]);
    const [selectedRFP, setSelectedRFP] = useState(null);
    const [proposalDraft, setProposalDraft] = useState('');
    const [critiqueResult, setCritiqueResult] = useState('');
    const [showProposal, setShowProposal] = useState(false);

    // Literature Review State
    const [reviewTopic, setReviewTopic] = useState('');
    const [reviewResult, setReviewResult] = useState('');

    const [loading, setLoading] = useState(false);

    const fetchMatches = useCallback(async (id) => {
        setLoading(true);
        try {
            const response = await client.post('/match/paper', { paper_id: id });
            setMatches(response.data.matches);
        } catch (err) {
            showToast('매칭 분석 중 오류가 발생했습니다.', 'error');
            console.error(err);
        } finally {
            setLoading(false);
        }
    }, [showToast]);

    // Notices 페이지에서 공고 데이터를 state로 전달받은 경우
    useEffect(() => {
        if (location.state?.from_notice) {
            setActiveTab('rfp_analysis');
            if (location.state.rfp_text) setRfpText(location.state.rfp_text);
            if (location.state.rfp_title) {
                showToast(`'${location.state.rfp_title}' 공고가 로드됐습니다.`, 'info');
            }
        }
    }, [location.state]); // eslint-disable-line react-hooks/exhaustive-deps

    useEffect(() => {
        if (paperId) {
            setActiveTab('paper_match');
            fetchMatches(paperId);
        }
    }, [paperId, fetchMatches]);

    const handleAnalyze = async () => {
        if (!rfpText.trim() || !profile.company_name) {
            showToast('공고문과 회사명을 입력해주세요.', 'warning');
            return;
        }
        setLoading(true);
        try {
            const response = await client.post('/analyze', {
                rfp_text: rfpText,
                user_profile: {
                    ...profile,
                    tech_keywords: profile.tech_keywords.split(',').map(k => k.trim())
                },
            });
            setAnalysisResult(response.data);
            showToast('분석이 완료되었습니다.', 'success');
        } catch {
            showToast('분석에 실패했습니다.', 'error');
        } finally {
            setLoading(false);
        }
    };

    const handleGenerateProposal = async (rfp) => {
        if (!paperId) {
            showToast("논문 ID가 없습니다.", 'error');
            return;
        }

        setLoading(true);
        setSelectedRFP(rfp);
        try {
            const response = await client.post('/proposal/generate', {
                paper_id: paperId,
                rfp_id: rfp.id
            });
            setProposalDraft(response.data.draft);
            setCritiqueResult(response.data.critique || '');
            setShowProposal(true);
        } catch (err) {
            showToast('제안서 생성 실패: ' + err.message, 'error');
        } finally {
            setLoading(false);
        }
    };

    const handleGenerateReview = async () => {
        if (!reviewTopic.trim()) {
            showToast('연구 주제를 입력해주세요.', 'warning');
            return;
        }
        setLoading(true);
        setReviewResult('');
        try {
            const response = await client.post('/api/agent/literature-review', {
                topic: reviewTopic
            });
            setReviewResult(response.data.report);
            showToast('문헌 고찰 생성 완료!', 'success');
        } catch (err) {
            showToast('문헌 고찰 생성 실패: ' + (err.response?.data?.detail || err.message), 'error');
        } finally {
            setLoading(false);
        }
    };

    // eslint-disable-next-line no-unused-vars
    const loadDemo = async () => {
        showToast("Paper Matching 데모는 업로드 페이지에서 시작하세요.", 'info');
    };

    const tabs = [
        { id: 'rfp_analysis', label: '공고 분석' },
        { id: 'paper_match', label: '논문 매칭' },
        { id: 'literature_review', label: '문헌 고찰 (AI)' },
    ];

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
                        {tabs.map(tab => (
                            <button
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id)}
                                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-300 ${
                                    activeTab === tab.id
                                        ? 'bg-primary/15 text-primary border border-primary/20'
                                        : 'text-white/35 hover:text-white/60 border border-transparent'
                                }`}
                            >
                                {tab.label}
                            </button>
                        ))}
                    </div>
                </div>

                {activeTab === 'literature_review' ? (
                    <div className="space-y-6 animate-fade-in">
                        <div className="bg-white/[0.03] backdrop-blur-xl border border-white/[0.06] rounded-2xl p-6" style={{ boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}>
                            <h2 className="font-display text-lg font-semibold text-white mb-3">💡 AI Literature Review 생성기</h2>
                            <p className="text-white/30 mb-5 text-sm leading-relaxed">관심 있는 연구 주제나 질병을 입력하면, 에이전트가 문헌을 검색해 종합적인 고찰(Review) 리포트를 작성합니다.</p>
                            <div className="flex gap-3">
                                <input
                                    className="glass-input flex-1"
                                    placeholder="예: CRISPR for Sickle Cell Disease"
                                    value={reviewTopic}
                                    onChange={e => setReviewTopic(e.target.value)}
                                    onKeyDown={(e) => e.key === 'Enter' && handleGenerateReview()}
                                />
                                <button
                                    onClick={handleGenerateReview}
                                    disabled={loading}
                                    className="glass-button px-6 disabled:opacity-40 font-semibold"
                                >
                                    {loading ? '검색 및 분석 중...' : '리뷰 생성'}
                                </button>
                            </div>
                        </div>

                        {loading && !reviewResult && (
                            <div className="bg-white/[0.02] border border-white/[0.06] rounded-2xl p-10 text-center">
                                <div className="inline-block animate-spin rounded-full h-10 w-10 border-2 border-white/10 border-t-primary mb-4"></div>
                                <h3 className="font-display text-base font-semibold text-white">AI가 학술 문헌을 검색하고 종합 중입니다...</h3>
                                <p className="text-white/25 mt-2 text-sm">이 작업은 수집된 문헌 양에 따라 10~30초 정도 소요될 수 있습니다.</p>
                            </div>
                        )}

                        {reviewResult && (
                            <div className="bg-surface/80 border border-white/[0.06] rounded-2xl p-8" style={{ boxShadow: '0 16px 48px rgba(0,0,0,0.5)' }}>
                                <div className="prose prose-invert max-w-none prose-headings:font-display prose-headings:text-white prose-p:text-white/70 prose-a:text-primary prose-strong:text-white">
                                    <ReactMarkdown>{reviewResult}</ReactMarkdown>
                                </div>
                            </div>
                        )}
                    </div>
                ) : activeTab === 'paper_match' ? (
                    <div className="space-y-6 animate-fade-in">
                        {paperTitle && (
                            <div className="bg-primary/[0.06] border border-primary/15 p-4 rounded-xl text-white/60 mb-6 flex items-center gap-2">
                                <span className="text-primary">📄</span> 분석 중인 논문: <span className="font-semibold text-white">{decodeURIComponent(paperTitle)}</span>
                            </div>
                        )}

                        <MatchingResults
                            matches={matches}
                            onSelect={handleGenerateProposal}
                            loading={loading && !proposalDraft}
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
                                    value={profile.company_name}
                                    onChange={e => setProfile({ ...profile, company_name: e.target.value })}
                                />
                                <input
                                    className="glass-input w-full"
                                    placeholder="보유 기술 (쉼표 구분)"
                                    value={profile.tech_keywords}
                                    onChange={e => setProfile({ ...profile, tech_keywords: e.target.value })}
                                />
                            </div>
                            <div className="bg-white/[0.03] backdrop-blur-xl border border-white/[0.06] rounded-2xl p-6" style={{ boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}>
                                <h2 className="font-display text-lg font-semibold text-white mb-4">📄 공고문 입력</h2>
                                <textarea
                                    className="glass-input w-full h-40 resize-none"
                                    placeholder="공고문 텍스트 붙여넣기..."
                                    value={rfpText}
                                    onChange={e => setRfpText(e.target.value)}
                                />
                                <button
                                    onClick={handleAnalyze}
                                    disabled={loading}
                                    className="glass-button mt-4 w-full py-3 font-semibold disabled:opacity-40"
                                >
                                    {loading ? '분석 중...' : '적합도 분석'}
                                </button>
                            </div>
                        </div>

                        {/* Analysis Result */}
                        <div className="space-y-6">
                            {analysisResult && (
                                <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-6 text-white" style={{ boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}>
                                    <h3 className="font-display text-lg font-bold mb-4">분석 결과: <span className="text-primary">{analysisResult.result.fit_grade}</span> 등급</h3>
                                    <p className="font-display text-4xl font-bold mb-2 text-gradient">{analysisResult.result.fit_score}점</p>
                                    <p className="text-white/50">{gradeLabels[analysisResult.result.fit_grade]}</p>
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* Proposal Modal */}
                {showProposal && selectedRFP && (
                    <Suspense
                        fallback={
                            <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center">
                                <div className="animate-spin rounded-full h-14 w-14 border-2 border-white/10 border-t-primary"></div>
                            </div>
                        }
                    >
                        <ProposalView
                            rfp={selectedRFP}
                            draft={proposalDraft}
                            critique={critiqueResult}
                            onClose={() => setShowProposal(false)}
                        />
                    </Suspense>
                )}

                {loading && showProposal && (
                    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center">
                        <div className="animate-spin rounded-full h-14 w-14 border-2 border-white/10 border-t-primary"></div>
                    </div>
                )}
            </div>
        </div>
    );
}
