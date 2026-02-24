
import React, { useState, useEffect } from 'react';
import { Sparkles, ArrowRight, ExternalLink } from 'lucide-react';
import api from '../../services/api';

export default function RecommendationList() {
    const [matches, setMatches] = useState([]);
    const [loading, setLoading] = useState(false);

    const fetchRecommendations = async () => {
        setLoading(true);
        try {
            const res = await api.get('/match/recommendations');
            setMatches(res.data);
        } catch (error) {
            console.error("Failed to load recommendations", error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchRecommendations();
    }, []);

    if (loading) return (
        <div className="p-6 text-center text-gray-400">
            <Sparkles className="w-8 h-8 text-primary mx-auto mb-2 animate-pulse" />
            <p>Analyzing company assets for best matches...</p>
        </div>
    );

    if (matches.length === 0) return (
        <div className="p-6 text-center text-gray-500 bg-black/20 rounded-xl border border-white/5">
            <p>No high-confidence matches found yet.</p>
            <p className="text-sm mt-2">Upload more IR/Paper assets to get better recommendations.</p>
        </div>
    );

    return (
        <div className="space-y-4">
            {matches.map((match) => (
                <div key={match.id} className="group relative bg-gradient-to-br from-white/5 to-white/0 p-5 rounded-xl border border-white/10 hover:border-primary/50 transition-all">
                    <div className="absolute top-4 right-4 flex items-center gap-2">
                        <span className={`px-2 py-1 rounded text-xs font-bold ${
                            match.score >= 90 ? 'bg-green-500/20 text-green-400' : 'bg-blue-500/20 text-blue-400'
                        }`}>
                            {match.score}% Match
                        </span>
                        <span className="text-xs text-gray-500 border border-white/10 px-2 py-1 rounded">
                            {match.source}
                        </span>
                    </div>

                    <h3 className="text-lg font-bold text-white mb-2 pr-20">{match.title}</h3>
                    <p className="text-sm text-gray-400 mb-3 line-clamp-2">{match.summary}</p>
                    
                    <div className="flex items-center gap-2 text-xs text-primary mb-4">
                        <Sparkles className="w-3 h-3" />
                        <span>{match.match_reason}</span>
                    </div>

                    <a 
                        href={match.url || "#"} 
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-2 text-sm font-medium text-white hover:text-primary transition-colors"
                    >
                        View Details <ExternalLink className="w-4 h-4" />
                    </a>
                </div>
            ))}
        </div>
    );
}
