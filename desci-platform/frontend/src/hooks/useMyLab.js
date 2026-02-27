import { useState, useEffect } from 'react';
import client from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';

/**
 * @typedef {Object} Paper
 * @property {string} id
 * @property {string} title
 * @property {string} [abstract]
 * @property {string} [ipfs_url]
 * @property {string} [cid]
 * @property {string} [type]
 * @property {string} [created_at]
 * @property {boolean} [nft_minted]
 */

/**
 * @typedef {Object} MintResult
 * @property {string} title
 * @property {string} message
 * @property {string} txHash
 */

/**
 * @typedef {Object} UseMyLabReturn
 * @property {Paper[]} papers
 * @property {boolean} isLoading
 * @property {Record<string, boolean>} mintingIds
 * @property {boolean} isSuccessModalOpen
 * @property {MintResult} mintResult
 * @property {(paper: Paper) => Promise<void>} mintNFT
 * @property {() => void} closeSuccessModal
 */

const EMPTY_MINT_RESULT = { title: '', message: '', txHash: '' };

/** @returns {UseMyLabReturn} */
export function useMyLab() {
    const { walletAddress } = useAuth();
    const { showToast } = useToast();

    const [papers, setPapers] = useState(/** @type {Paper[]} */ ([]));
    const [isLoading, setIsLoading] = useState(true);
    const [mintingIds, setMintingIds] = useState(/** @type {Record<string, boolean>} */ ({}));
    const [isSuccessModalOpen, setIsSuccessModalOpen] = useState(false);
    const [mintResult, setMintResult] = useState(/** @type {MintResult} */ (EMPTY_MINT_RESULT));

    useEffect(() => {
        client.get('/papers/me')
            .then(res => setPapers(res.data))
            .catch(() => showToast('연구 데이터를 불러오는데 실패했습니다.', 'error'))
            .finally(() => setIsLoading(false));
    }, [showToast]);

    /** @param {Paper} paper */
    const mintNFT = async (paper) => {
        if (!walletAddress) {
            showToast('지갑이 연결되지 않았습니다. Wallet 페이지에서 연결해주세요.', 'warning');
            return;
        }
        if (!paper.ipfs_url) {
            showToast('IPFS URL이 없습니다. 논문 업로드가 완전히 완료된 후 민팅하세요.', 'warning');
            return;
        }

        setMintingIds(prev => ({ ...prev, [paper.id]: true }));
        try {
            const res = await client.post('/nft/mint', {
                user_address: walletAddress,
                token_uri: paper.ipfs_url,
            });

            const succeeded = res.data?.success === true || !!res.data?.tx_hash;
            if (succeeded) {
                setMintResult({
                    title: 'NFT Minted Successfully! 💎',
                    message: `"${paper.title}"의 IP-NFT가 블록체인에 민팅되었습니다.`,
                    txHash: res.data.tx_hash || '',
                });
                setIsSuccessModalOpen(true);
                setPapers(prev => prev.map(p =>
                    p.id === paper.id ? { ...p, nft_minted: true } : p
                ));
            } else {
                const reason = res.data?.error || res.data?.detail || '알 수 없는 오류';
                showToast(`민팅 실패: ${reason}`, 'error');
            }
        } catch (err) {
            showToast(`민팅 오류: ${err.response?.data?.detail || err.message || '서버 오류'}`, 'error');
            console.error('[mintNFT]', err);
        } finally {
            setMintingIds(prev => ({ ...prev, [paper.id]: false }));
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
    };
}
