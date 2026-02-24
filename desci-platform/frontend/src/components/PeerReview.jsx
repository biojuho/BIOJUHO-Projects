/**
 * Peer Review Workflow Page
 * Browse available papers and submit reviews for token rewards
 */
import { useState, useEffect } from 'react';
import client from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';
import GlassCard from './ui/GlassCard';
import ReactMarkdown from 'react-markdown';
import {
    FileText,
    Star,
    Send,
    Loader2,
    Award,
    ChevronDown,
    ChevronUp,
    ExternalLink
} from 'lucide-react';

export default function PeerReview() {
    const { walletAddress } = useAuth();
    const { showToast } = useToast();
    const [papers, setPapers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [expandedPaper, setExpandedPaper] = useState(null);
    const [reviewText, setReviewText] = useState('');
    const [rating, setRating] = useState(3);
    const [submitting, setSubmitting] = useState(false);

    useEffect(() => {
        fetchPapers();
    }, []);

    const fetchPapers = async () => {
        try {
            // Use papers/me for now - in production this would be a separate endpoint for reviewable papers
            const res = await client.get('/papers/me');
            setPapers(res.data || []);
        } catch (err) {
            console.error('Failed to fetch papers:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleSubmitReview = async () => {
        if (!reviewText.trim()) {
            showToast('리뷰 내용을 입력해주세요.', 'warning');
            return;
        }

        setSubmitting(true);
        try {
            // Submit the review (would be a real endpoint in production)
            // For now, we trigger the reward directly
            if (walletAddress) {
                await client.post(`/reward/review?user_address=${walletAddress}`);
                showToast('리뷰가 제출되었습니다! 50 DSCI 보상이 지급됩니다.', 'success');
            } else {
                showToast('리뷰가 저장되었습니다. 지갑을 연결하면 보상을 받을 수 있습니다.', 'info');
            }
            setReviewText('');
            setRating(3);
            setExpandedPaper(null);
        } catch (err) {
            showToast('리뷰 제출 실패: ' + (err.response?.data?.detail || err.message), 'error');
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
                <div>
                    <p className="text-xs text-white/30 uppercase tracking-[0.2em] font-medium mb-2">Community</p>
                    <h1 className="font-display text-3xl font-bold text-white tracking-tight">
                        Peer <span className="text-gradient">Review</span>
                    </h1>
                    <p className="text-white/30 text-sm mt-1">논문을 리뷰하고 50 DSCI 토큰 보상을 받으세요</p>
                </div>
                <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-highlight/[0.08] border border-highlight/20 text-highlight text-sm font-medium">
                    <Award className="w-4 h-4" />
                    리뷰 1건당 +50 DSCI
                </div>
            </div>

            {/* Papers List */}
            {loading ? (
                <div className="flex items-center justify-center py-20">
                    <div className="animate-spin rounded-full h-10 w-10 border-2 border-white/10 border-t-primary"></div>
                </div>
            ) : papers.length === 0 ? (
                <GlassCard className="p-12 text-center">
                    <FileText className="w-12 h-12 text-white/10 mx-auto mb-4" />
                    <h3 className="font-display text-lg font-semibold text-white/60 mb-2">리뷰 가능한 논문이 없습니다</h3>
                    <p className="text-white/25 text-sm">논문이 업로드되면 여기에 표시됩니다.</p>
                </GlassCard>
            ) : (
                <div className="space-y-4">
                    {papers.map((paper) => (
                        <GlassCard key={paper.id} className="overflow-hidden">
                            {/* Paper Header */}
                            <div
                                className="p-5 cursor-pointer hover:bg-white/[0.02] transition-colors"
                                onClick={() => setExpandedPaper(expandedPaper === paper.id ? null : paper.id)}
                            >
                                <div className="flex items-start justify-between gap-4">
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-2">
                                            <span className="badge-primary text-[10px]">
                                                {paper.reward_claimed ? 'Reviewed' : 'Open for Review'}
                                            </span>
                                        </div>
                                        <h3 className="font-display text-base font-semibold text-white line-clamp-2">
                                            {paper.title}
                                        </h3>
                                        {paper.abstract && (
                                            <p className="text-white/30 text-sm mt-2 line-clamp-2">{paper.abstract}</p>
                                        )}
                                        <div className="flex items-center gap-3 mt-3 text-xs text-white/20">
                                            {paper.cid && (
                                                <span className="font-mono">CID: {paper.cid.slice(0, 12)}...</span>
                                            )}
                                            {paper.ipfs_url && (
                                                <a
                                                    href={paper.ipfs_url}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="flex items-center gap-1 text-primary hover:text-primary-300 transition-colors"
                                                    onClick={e => e.stopPropagation()}
                                                >
                                                    <ExternalLink className="w-3 h-3" /> IPFS
                                                </a>
                                            )}
                                        </div>
                                    </div>
                                    <div className="text-white/20">
                                        {expandedPaper === paper.id ? (
                                            <ChevronUp className="w-5 h-5" />
                                        ) : (
                                            <ChevronDown className="w-5 h-5" />
                                        )}
                                    </div>
                                </div>
                            </div>

                            {/* Review Form (Expanded) */}
                            {expandedPaper === paper.id && (
                                <div className="border-t border-white/[0.06] p-5 bg-white/[0.01] animate-fade-in">
                                    <h4 className="font-display text-sm font-semibold text-white mb-4">Write Your Review</h4>

                                    {/* Rating */}
                                    <div className="mb-4">
                                        <label className="text-xs text-white/30 uppercase tracking-wider mb-2 block">Quality Rating</label>
                                        <div className="flex gap-1">
                                            {[1, 2, 3, 4, 5].map(n => (
                                                <button
                                                    key={n}
                                                    type="button"
                                                    onClick={() => setRating(n)}
                                                    className="p-1 transition-colors"
                                                >
                                                    <Star
                                                        className={`w-6 h-6 ${n <= rating ? 'text-highlight fill-highlight' : 'text-white/10'}`}
                                                    />
                                                </button>
                                            ))}
                                            <span className="ml-2 text-sm text-white/40 self-center">{rating}/5</span>
                                        </div>
                                    </div>

                                    {/* Review Text */}
                                    <textarea
                                        className="glass-input w-full h-32 resize-none mb-4"
                                        placeholder="논문의 강점, 약점, 개선점을 작성해주세요..."
                                        value={reviewText}
                                        onChange={e => setReviewText(e.target.value)}
                                    />

                                    {/* Preview */}
                                    {reviewText && (
                                        <div className="mb-4 p-4 bg-white/[0.02] rounded-xl border border-white/[0.04]">
                                            <p className="text-[11px] text-white/20 uppercase tracking-wider mb-2">Preview</p>
                                            <div className="prose prose-invert prose-sm max-w-none text-white/60">
                                                <ReactMarkdown>{reviewText}</ReactMarkdown>
                                            </div>
                                        </div>
                                    )}

                                    <div className="flex items-center justify-between">
                                        <p className="text-xs text-white/20">
                                            리뷰 제출 시 <span className="text-highlight font-semibold">+50 DSCI</span> 보상 지급
                                        </p>
                                        <button
                                            onClick={() => handleSubmitReview(paper.id)}
                                            disabled={submitting || !reviewText.trim()}
                                            className="glass-button px-5 py-2.5 font-semibold flex items-center gap-2 disabled:opacity-40"
                                        >
                                            {submitting ? (
                                                <><Loader2 className="w-4 h-4 animate-spin" /> 제출 중...</>
                                            ) : (
                                                <><Send className="w-4 h-4" /> 리뷰 제출</>
                                            )}
                                        </button>
                                    </div>
                                </div>
                            )}
                        </GlassCard>
                    ))}
                </div>
            )}
        </div>
    );
}
