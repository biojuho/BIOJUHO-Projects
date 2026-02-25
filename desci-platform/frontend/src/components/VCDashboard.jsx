import React, { useState, useEffect } from 'react';
import api from '../services/api';

const VCDashboard = () => {
    const [vcList, setVcList] = useState([]);
    const [selectedVc, setSelectedVc] = useState(null);
    const [matches, setMatches] = useState([]);
    const [analyzing, setAnalyzing] = useState(false);
    const [detailMatch, setDetailMatch] = useState(null);

    // 1. Fetch VC List on Mount
    useEffect(() => {
        const fetchVcs = async () => {
            try {
                const response = await api.get('/vc/list');
                setVcList(response.data);
            } catch (error) {
                console.error("Failed to fetch VC list:", error);
            }
        };
        fetchVcs();
    }, []);

    // 2. Fetch Recommendations when VC is selected
    useEffect(() => {
        if (!selectedVc) return;

        const fetchMatches = async () => {
            setAnalyzing(true);
            try {
                const response = await api.get(`/vc/recommendations/${selectedVc.id}`);
                setMatches(response.data);
            } catch (error) {
                console.error("Failed to fetch matches:", error);
            } finally {
                setAnalyzing(false);
            }
        };

        fetchMatches();
    }, [selectedVc]);

    return (
        <React.Fragment>
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">

                {/* Header Section */}
                <div className="mb-8 p-6 bg-white/5 backdrop-blur-xl rounded-xl shadow-2xl border border-white/10 relative overflow-hidden">
                    <h1 className="text-4xl font-extrabold bg-clip-text text-transparent bg-gradient-to-r from-purple-400 to-pink-600 mb-2">
                        DeSci VC Portal
                    </h1>
                    <p className="text-gray-400 text-lg">
                        View the platform through the lens of a Venture Capitalist. Select a firm to see AI-matched deal flow.
                    </p>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mb-8">
                    {/* Selector */}
                    <div className="lg:col-span-4 bg-white/5 backdrop-blur-lg rounded-xl p-6 border border-white/10 shadow-lg h-fit">
                        <label className="block text-sm font-medium text-gray-400 mb-2">Select VC Firm</label>
                        <select
                            className="w-full bg-black/40 backdrop-blur-md border border-white/10 text-white rounded-lg px-4 py-3 appearance-none focus:ring-2 focus:ring-purple-500 outline-none transition-all duration-200"
                            onChange={(e) => {
                                const vc = vcList.find(v => v.id === e.target.value);
                                setSelectedVc(vc);
                            }}
                            value={selectedVc?.id || ""}
                        >
                            <option value="" disabled>-- Choose a VC --</option>
                            {vcList.map(vc => (
                                <option key={vc.id} value={vc.id}>
                                    {vc.name} ({vc.country})
                                </option>
                            ))}
                        </select>
                         {!selectedVc && (
                            <div className="mt-4 p-4 bg-blue-900/20 border border-blue-800 rounded-lg">
                                <p className="text-sm text-blue-300">
                                    💡 Select a firm to load their investment thesis and see matched startups.
                                </p>
                            </div>
                        )}
                    </div>

                    {/* VC Profile View */}
                    {selectedVc && (
                        <div className="lg:col-span-8 bg-white/5 backdrop-blur-lg rounded-xl p-6 border border-white/10 shadow-lg relative overflow-hidden transition-all duration-500 ease-in-out transform">
                            <div className="absolute top-0 right-0 p-4 opacity-10">
                                <svg className="w-32 h-32 text-purple-500" fill="currentColor" viewBox="0 0 24 24">
                                    <path d="M12 2L2 7l10 5 10-5-10-5zm0 9l2.5-1.25L12 8.5l-2.5 1.25L12 11zm0 2.5l-5-2.5-5 2.5L12 22l10-8.5-5-2.5-5 2.5z" />
                                </svg>
                            </div>
                            <div className="relative z-10">
                                <h2 className="text-2xl font-bold text-white mb-2">{selectedVc.name}</h2>
                                <div className="flex flex-wrap gap-2 mb-4">
                                    {selectedVc.preferred_stages.map(stage => (
                                        <span key={stage} className="px-2 py-1 text-xs font-semibold bg-blue-900 text-blue-200 rounded-full border border-blue-700">
                                            {stage}
                                        </span>
                                    ))}
                                </div>
                                <div className="bg-gray-900/50 p-4 rounded-lg border border-gray-700 mb-4">
                                    <h3 className="text-sm text-gray-400 font-semibold mb-1">Investment Thesis</h3>
                                    <p className="text-gray-300 italic">"{selectedVc.investment_thesis}"</p>
                                </div>
                                <div className="flex flex-wrap gap-2">
                                    <span className="text-sm text-gray-500 py-1">Focus Areas:</span>
                                    {selectedVc.portfolio_keywords.map(kw => (
                                        <span key={kw} className="px-2 py-1 text-xs bg-gray-700 text-gray-300 rounded border border-gray-600">
                                            #{kw}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                {/* Matches Grid */}
                {selectedVc && (
                    <div className="transition-opacity duration-500 ease-in-out">
                        <h3 className="text-2xl font-bold text-white mb-6 flex items-center">
                            <span className="bg-clip-text text-transparent bg-gradient-to-r from-green-400 to-emerald-600 mr-2">
                                AI Sourced Deal Flow
                            </span>
                            {analyzing && (
                                <span className="flex h-3 w-3 relative ml-3">
                                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-purple-400 opacity-75"></span>
                                    <span className="relative inline-flex rounded-full h-3 w-3 bg-purple-500"></span>
                                </span>
                            )}
                        </h3>

                        {analyzing ? (
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                {[1, 2, 3].map(i => (
                                    <div key={i} className="bg-gray-800 rounded-xl h-64 animate-pulse border border-gray-700"></div>
                                ))}
                            </div>
                        ) : matches.length === 0 ? (
                            <div className="text-center py-20 bg-gray-800/50 rounded-xl border border-gray-700 border-dashed">
                                <svg className="mx-auto h-12 w-12 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                                <p className="mt-4 text-gray-400 text-lg">No matches found for this thesis yet.</p>
                                <p className="text-gray-600">Try uploading more assets or adjusting the thesis.</p>
                            </div>
                        ) : (
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                {matches.map((match) => (
                                    <div key={match.asset_id} onClick={() => setDetailMatch(match)} className="bg-white/5 backdrop-blur-lg rounded-xl overflow-hidden border border-white/10 hover:border-purple-500 transition-all duration-300 hover:shadow-[0_0_25px_rgba(168,85,247,0.2)] shadow-lg group flex flex-col cursor-pointer h-full transform hover:-translate-y-1">
                                        <div className="p-6 flex-grow">
                                            <div className="flex justify-between items-start mb-4">
                                                <div className="bg-gray-700 p-2 rounded-lg shadow-inner">
                                                    <svg className="w-8 h-8 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                                                    </svg>
                                                </div>
                                                <div className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wide shadow-sm ${match.score >= 90 ? 'bg-green-900/80 text-green-300 border border-green-700' :
                                                        match.score >= 80 ? 'bg-blue-900/80 text-blue-300 border border-blue-700' :
                                                            'bg-yellow-900/80 text-yellow-300 border border-yellow-700'
                                                    }`}>
                                                    {match.score}% Fit
                                                </div>
                                            </div>

                                            <h4 className="text-xl font-bold text-white mb-2 group-hover:text-purple-400 transition-colors line-clamp-2">
                                                {match.title}
                                            </h4>

                                            <p className="text-gray-400 text-sm mb-4 line-clamp-3 leading-relaxed">
                                                {match.summary}
                                            </p>

                                            <div className="space-y-3">
                                                <div className="bg-black/20 p-3 rounded-lg border border-white/5">
                                                    <p className="text-xs text-purple-300 font-semibold mb-1 uppercase tracking-wider">Why it matches</p>
                                                    <p className="text-xs text-gray-400 leading-snug">{match.match_reason}</p>
                                                </div>

                                                <div className="flex flex-wrap gap-1">
                                                    {match.keywords?.slice(0, 3).map(k => (
                                                        <span key={k} className="text-xs text-gray-500 bg-gray-900 px-2 py-1 rounded border border-gray-700">
                                                            {k}
                                                        </span>
                                                    ))}
                                                </div>
                                            </div>
                                        </div>

                                        <div className="px-6 py-4 bg-black/30 border-t border-white/10 flex justify-between items-center mt-auto">
                                            <span className="text-xs text-gray-500">Source: BioLinker DB</span>
                                            <button
                                                onClick={e => { e.stopPropagation(); setDetailMatch(match); }}
                                                className="text-sm text-purple-400 hover:text-white font-medium transition-colors group-hover:translate-x-1 duration-200 flex items-center"
                                            >
                                                View Details
                                                <svg className="w-4 h-4 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                                </svg>
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}

            </div>
        {/* Detail Modal */}
        {detailMatch && (
            <div
                className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
                onClick={() => setDetailMatch(null)}
            >
                <div
                    className="bg-gray-900 border border-white/10 rounded-2xl max-w-2xl w-full max-h-[85vh] overflow-y-auto shadow-2xl"
                    onClick={e => e.stopPropagation()}
                >
                    {/* Modal Header */}
                    <div className="flex items-start justify-between p-6 border-b border-white/10">
                        <div className="flex-1 pr-4">
                            <div className={`inline-flex px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wide mb-3 ${
                                detailMatch.score >= 90 ? 'bg-green-900/80 text-green-300 border border-green-700' :
                                detailMatch.score >= 80 ? 'bg-blue-900/80 text-blue-300 border border-blue-700' :
                                'bg-yellow-900/80 text-yellow-300 border border-yellow-700'
                            }`}>
                                {detailMatch.score}% Fit Score
                            </div>
                            <h2 className="text-xl font-bold text-white leading-snug">{detailMatch.title}</h2>
                        </div>
                        <button
                            onClick={() => setDetailMatch(null)}
                            className="text-gray-500 hover:text-white transition-colors shrink-0 p-1"
                        >
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>
                    </div>

                    {/* Modal Body */}
                    <div className="p-6 space-y-5">
                        {/* Summary */}
                        <div>
                            <h3 className="text-xs text-gray-400 font-semibold uppercase tracking-wider mb-2">Summary</h3>
                            <p className="text-gray-300 leading-relaxed text-sm">{detailMatch.summary}</p>
                        </div>

                        {/* Match Reason */}
                        <div className="bg-purple-900/20 border border-purple-700/30 rounded-xl p-4">
                            <h3 className="text-xs text-purple-300 font-semibold uppercase tracking-wider mb-2">Why It Matches This Thesis</h3>
                            <p className="text-gray-300 text-sm leading-relaxed">{detailMatch.match_reason}</p>
                        </div>

                        {/* Keywords */}
                        {detailMatch.keywords?.length > 0 && (
                            <div>
                                <h3 className="text-xs text-gray-400 font-semibold uppercase tracking-wider mb-2">Keywords</h3>
                                <div className="flex flex-wrap gap-2">
                                    {detailMatch.keywords.map(k => (
                                        <span key={k} className="text-xs text-gray-300 bg-gray-800 px-3 py-1.5 rounded-lg border border-gray-700">
                                            {k}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Source */}
                        <div className="flex items-center justify-between pt-2 border-t border-white/5 text-xs text-gray-500">
                            <span>Source: BioLinker DB</span>
                            {detailMatch.asset_id && (
                                <span className="font-mono">ID: {detailMatch.asset_id.slice(0, 12)}...</span>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        )}
    </React.Fragment>
    );
};

export default VCDashboard;
