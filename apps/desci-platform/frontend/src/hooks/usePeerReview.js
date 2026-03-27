import { useState, useEffect } from 'react';
import client from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';
import { useLocale } from '../contexts/LocaleContext';

export function usePeerReview() {
    const { walletAddress } = useAuth();
    const { showToast } = useToast();
    const { t } = useLocale();

    const [papers, setPapers] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [expandedPaperId, setExpandedPaperId] = useState(null);
    const [reviewText, setReviewText] = useState('');
    const [rating, setRating] = useState(3);
    const [isSubmitting, setIsSubmitting] = useState(false);

    useEffect(() => {
        client.get('/papers/me')
            .then((response) => setPapers(response.data || []))
            .catch((error) => console.error('Failed to fetch papers:', error))
            .finally(() => setIsLoading(false));
    }, []);

    const togglePaper = (paperId) => {
        setExpandedPaperId((prev) => (prev === paperId ? null : paperId));
    };

    const submitReview = async () => {
        if (!reviewText.trim()) {
            showToast(t('peerReview.reviewRequired'), 'warning');
            return;
        }

        if (!expandedPaperId) {
            showToast(t('peerReview.selectPaper'), 'warning');
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

            showToast(walletAddress ? t('peerReview.submitSuccessWallet') : t('peerReview.submitSuccessNoWallet'), walletAddress ? 'success' : 'info');

            setReviewText('');
            setRating(3);
            setExpandedPaperId(null);
            setPapers((prev) => prev.map((paper) => (paper.id === expandedPaperId ? { ...paper, reward_claimed: true } : paper)));
        } catch (err) {
            showToast(t('peerReview.submitFailed', { message: err.response?.data?.detail || err.message }), 'error');
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
        t,
    };
}
