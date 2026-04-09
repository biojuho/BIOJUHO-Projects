import { useState, useEffect, useRef } from 'react';
import client from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';
import { useLocale } from '../contexts/LocaleContext';

const EMPTY_MINT_RESULT = { title: '', message: '', txHash: '' };

export function useMyLab() {
    const { walletAddress } = useAuth();
    const { showToast } = useToast();
    const { t } = useLocale();
    const showToastRef = useRef(showToast);
    const tRef = useRef(t);

    showToastRef.current = showToast;
    tRef.current = t;

    const [papers, setPapers] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [mintingIds, setMintingIds] = useState({});
    const [isSuccessModalOpen, setIsSuccessModalOpen] = useState(false);
    const [mintResult, setMintResult] = useState(EMPTY_MINT_RESULT);

    useEffect(() => {
        let cancelled = false;

        client.get('/papers/me')
            .then((response) => {
                if (!cancelled) {
                    setPapers(response.data);
                }
            })
            .catch(() => {
                if (!cancelled) {
                    showToastRef.current(tRef.current('myLab.loadFailed'), 'error');
                }
            })
            .finally(() => {
                if (!cancelled) {
                    setIsLoading(false);
                }
            });

        return () => {
            cancelled = true;
        };
    }, []);

    const mintNFT = async (paper) => {
        if (!walletAddress) {
            showToast(t('myLab.walletMissing'), 'warning');
            return;
        }

        if (!paper.ipfs_url) {
            showToast(t('myLab.ipfsMissing'), 'warning');
            return;
        }

        setMintingIds((prev) => ({ ...prev, [paper.id]: true }));
        try {
            const response = await client.post('/nft/mint', {
                user_address: walletAddress,
                token_uri: paper.ipfs_url,
            });

            const succeeded = response.data?.success === true || !!response.data?.tx_hash;
            if (succeeded) {
                setMintResult({
                    title: t('myLab.mintedSuccessTitle'),
                    message: t('myLab.mintedSuccessBody', { title: paper.title }),
                    txHash: response.data.tx_hash || '',
                });
                setIsSuccessModalOpen(true);
                setPapers((prev) => prev.map((item) => (item.id === paper.id ? { ...item, nft_minted: true } : item)));
            } else {
                const reason = response.data?.error || response.data?.detail || t('common.unknownError');
                showToast(t('myLab.mintFailed', { message: reason }), 'error');
            }
        } catch (err) {
            showToast(t('myLab.mintFailed', { message: err.response?.data?.detail || err.message || t('common.unknownError') }), 'error');
            console.error('[mintNFT]', err);
        } finally {
            setMintingIds((prev) => ({ ...prev, [paper.id]: false }));
        }
    };

    return {
        papers,
        isLoading,
        mintingIds,
        isSuccessModalOpen,
        mintResult,
        mintNFT,
        closeSuccessModal: () => setIsSuccessModalOpen(false),
        t,
    };
}
