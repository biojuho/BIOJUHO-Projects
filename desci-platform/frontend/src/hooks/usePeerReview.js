import { useState, useEffect } from 'react';
import client from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';

/**
 * @typedef {Object} ReviewablePaper
 * @property {string} id
 * @property {string} title
 * @property {string} [abstract]
 * @property {string} [ipfs_url]
 * @property {string} [cid]
 * @property {boolean} [reward_claimed]
 */

/**
 * @typedef {Object} UsePeerReviewReturn
 * @property {ReviewablePaper[]} papers
 * @property {boolean} isLoading
 * @property {string | null} expandedPaperId
 * @property {string} reviewText
 * @property {number} rating
 * @property {boolean} isSubmitting
 * @property {(paperId: string) => void} togglePaper
 * @property {(text: string) => void} setReviewText
 * @property {(rating: number) => void} setRating
 * @property {() => Promise<void>} submitReview
 */

/** @returns {UsePeerReviewReturn} */
export function usePeerReview() {
    const { walletAddress } = useAuth();
    const { showToast } = useToast();

    const [papers, setPapers] = useState(/** @type {ReviewablePaper[]} */ ([]));
    const [isLoading, setIsLoading] = useState(true);
    const [expandedPaperId, setExpandedPaperId] = useState(/** @type {string | null} */ (null));
    const [reviewText, setReviewText] = useState('');
    const [rating, setRating] = useState(3);
    const [isSubmitting, setIsSubmitting] = useState(false);

    useEffect(() => {
        client.get('/papers/me')
            .then(res => setPapers(res.data || []))
            .catch(err => console.error('Failed to fetch papers:', err))
            .finally(() => setIsLoading(false));
    }, []);

    /** @param {string} paperId */
    const togglePaper = (paperId) => {
        setExpandedPaperId(prev => prev === paperId ? null : paperId);
    };

    const submitReview = async () => {
        if (!reviewText.trim()) {
            showToast('리뷰 내용을 입력해주세요.', 'warning');
            return;
        }
        if (!expandedPaperId) {
            showToast('리뷰할 논문을 선택해주세요.', 'warning');
            return;
        }

        setIsSubmitting(true);
        try {
            const params = new URLSearchParams({ paper_id: expandedPaperId, rating: String(rating) });
            if (walletAddress) params.set('user_address', walletAddress);

            await client.post(`/reward/review?${params}`, {
                paper_id: expandedPaperId,
                review_text: reviewText,
                rating,
            });

            if (walletAddress) {
                showToast('리뷰가 제출되었습니다! 50 DSCI 보상이 지급됩니다.', 'success');
            } else {
                showToast('리뷰가 저장되었습니다. 지갑을 연결하면 보상을 받을 수 있습니다.', 'info');
            }

            setReviewText('');
            setRating(3);
            setExpandedPaperId(null);
            setPapers(prev => prev.map(p =>
                p.id === expandedPaperId ? { ...p, reward_claimed: true } : p
            ));
        } catch (err) {
            showToast(`리뷰 제출 실패: ${err.response?.data?.detail || err.message}`, 'error');
        } finally {
            setIsSubmitting(false);
        }
    };

    return {
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
    };
}
