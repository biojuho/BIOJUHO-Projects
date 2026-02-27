import { useState, useEffect } from 'react';
import api from '../services/api';

/**
 * @typedef {Object} VCFirm
 * @property {string} id
 * @property {string} name
 * @property {string} country
 * @property {string[]} preferred_stages
 * @property {string} investment_thesis
 * @property {string[]} portfolio_keywords
 */

/**
 * @typedef {Object} DealMatch
 * @property {string} asset_id
 * @property {string} title
 * @property {string} summary
 * @property {string} match_reason
 * @property {number} score
 * @property {string[]} keywords
 */

/**
 * @typedef {Object} UseVCDashboardReturn
 * @property {VCFirm[]} vcList
 * @property {VCFirm | null} selectedVc
 * @property {DealMatch[]} matches
 * @property {boolean} isLoadingMatches
 * @property {DealMatch | null} activeDetail
 * @property {(vc: VCFirm) => void} selectVc
 * @property {(match: DealMatch) => void} openDetail
 * @property {() => void} closeDetail
 */

/** @returns {UseVCDashboardReturn} */
export function useVCDashboard() {
    const [vcList, setVcList] = useState(/** @type {VCFirm[]} */ ([]));
    const [selectedVc, setSelectedVc] = useState(/** @type {VCFirm | null} */ (null));
    const [matches, setMatches] = useState(/** @type {DealMatch[]} */ ([]));
    const [isLoadingMatches, setIsLoadingMatches] = useState(false);
    const [activeDetail, setActiveDetail] = useState(/** @type {DealMatch | null} */ (null));

    useEffect(() => {
        api.get('/vc/list')
            .then(res => setVcList(res.data))
            .catch(err => console.error('Failed to fetch VC list:', err));
    }, []);

    useEffect(() => {
        if (!selectedVc) return;

        setIsLoadingMatches(true);
        api.get(`/vc/recommendations/${selectedVc.id}`)
            .then(res => setMatches(res.data))
            .catch(err => console.error('Failed to fetch VC matches:', err))
            .finally(() => setIsLoadingMatches(false));
    }, [selectedVc]);

    return {
        vcList,
        selectedVc,
        matches,
        isLoadingMatches,
        activeDetail,
        selectVc: setSelectedVc,
        openDetail: setActiveDetail,
        closeDetail: () => setActiveDetail(null),
    };
}
