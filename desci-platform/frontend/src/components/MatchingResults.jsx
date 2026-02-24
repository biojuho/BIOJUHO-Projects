/**
 * MatchingResults Component
 * Displays a list of RFPs matched to a paper.
 */
import React from 'react';

const MatchingResults = ({ matches, onSelect, loading }) => {
    if (loading) {
        return (
            <div className="text-center py-12">
                <div className="animate-spin rounded-full h-10 w-10 border-2 border-white/10 border-t-primary mx-auto mb-4"></div>
                <p className="text-primary/70">AI가 논문을 분석하여 최적의 공고를 찾고 있습니다...</p>
            </div>
        );
    }

    if (!matches || matches.length === 0) {
        return (
            <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-8 text-center">
                <p className="text-white/30">매칭된 공고가 없습니다.</p>
            </div>
        );
    }

    return (
        <div className="space-y-4">
            <h2 className="font-display text-xl font-bold text-white mb-4">🎯 AI 매칭 결과</h2>
            <div className="grid gap-4">
                {matches.map((match) => (
                    <div
                        key={match.id}
                        className="bg-white/[0.03] backdrop-blur-xl border border-white/[0.06] rounded-xl p-6 hover:bg-white/[0.06] hover:border-white/[0.1] transition-all cursor-pointer group"
                        style={{ boxShadow: '0 4px 20px rgba(0,0,0,0.3)' }}
                        onClick={() => onSelect(match)}
                    >
                        <div className="flex justify-between items-start mb-2">
                            <span className={`px-2 py-1 rounded text-xs font-bold ${match.metadata.source === 'KDDF' ? 'bg-accent/10 text-accent-light border border-accent/15' : 'bg-primary/10 text-primary border border-primary/15'
                                }`}>
                                {match.metadata.source}
                            </span>
                            <div className="flex items-center gap-2">
                                <span className="text-white/25 text-sm">유사도</span>
                                <span className="text-primary font-bold font-display">{(match.similarity * 100).toFixed(1)}%</span>
                            </div>
                        </div>

                        <h3 className="font-display text-lg font-semibold text-white mb-2 group-hover:text-primary transition-colors">
                            {match.metadata.title}
                        </h3>

                        <p className="text-white/35 text-sm line-clamp-2 mb-4">
                            {match.document}
                        </p>

                        <div className="flex justify-between items-center text-sm">
                            <div className="flex gap-2">
                                {match.metadata.keywords.split(',').slice(0, 3).map((kw, i) => (
                                    <span key={i} className="text-white/20">#{kw.trim()}</span>
                                ))}
                            </div>
                            <button className="text-primary hover:text-primary-300 font-medium flex items-center gap-1 transition-colors">
                                제안서 작성하기 📝
                            </button>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default MatchingResults;
