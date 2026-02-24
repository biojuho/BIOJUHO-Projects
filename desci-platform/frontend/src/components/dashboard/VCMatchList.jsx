import React, { useEffect, useState } from 'react';
import { Building2, Globe, TrendingUp, ChevronRight } from 'lucide-react';
// eslint-disable-next-line no-unused-vars
import { motion, AnimatePresence } from 'framer-motion';
import api from '../../services/api'; // Ensure this path is correct based on project structure

export default function VCMatchList() {
    const [matches, setMatches] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchMatches = async () => {
            try {
                // Using relative path assuming proxy or same origin, otherwise use API_BASE_URL
                const response = await api.get('/match/vc');
                setMatches(response.data);
            } catch (err) {
                console.error("VC Match Error:", err);
                setError("Failed to load investment pairs.");
            } finally {
                setLoading(false);
            }
        };

        fetchMatches();
    }, []);

    if (loading) return (
        <div className="flex justify-center p-8">
            <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-purple-500"></div>
        </div>
    );

    if (error) return (
        <div className="p-4 text-center text-red-400 bg-red-900/10 rounded-xl border border-red-900/20">
            {error}
        </div>
    );

    if (matches.length === 0) return (
        <div className="p-8 text-center text-gray-400">
            <Building2 className="w-12 h-12 mx-auto mb-3 opacity-20" />
            <p>No investment matches found yet.</p>
            <p className="text-sm">Upload your IR deck to get started.</p>
        </div>
    );

    return (
        <div className="space-y-4">
            <AnimatePresence>
                {matches.map((vc, index) => (
                    <motion.div
                        key={vc.id || index}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.1 }}
                        className="group relative overflow-hidden rounded-xl bg-gradient-to-br from-white/5 to-white/0 border border-white/10 hover:border-purple-500/30 transition-all duration-300"
                    >
                        <div className="p-5 flex items-start gap-4">
                            {/* Score Badge */}
                            <div className="flex-shrink-0 flex flex-col items-center">
                                <div className={`
                                    w-12 h-12 rounded-full flex items-center justify-center font-bold text-sm
                                    ${vc.score >= 80 ? 'bg-green-500/20 text-green-400 border border-green-500/30' : 
                                      'bg-blue-500/20 text-blue-400 border border-blue-500/30'}
                                `}>
                                    {vc.score}
                                </div>
                                <span className="text-[10px] text-gray-500 mt-1">MATCH</span>
                            </div>

                            {/* Content */}
                            <div className="flex-grow min-w-0">
                                <div className="flex items-center justify-between mb-1">
                                    <h4 className="font-semibold text-lg text-white group-hover:text-purple-400 transition-colors truncate">
                                        {vc.name}
                                    </h4>
                                    {/* Country Badge */}
                                    <span className="flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-white/5 text-gray-400 border border-white/5">
                                        <Globe className="w-3 h-3" />
                                        {vc.country || "Global"}
                                    </span>
                                </div>
                                
                                <p className="text-sm text-gray-300 line-clamp-2 mb-2">
                                    {vc.thesis_summary || vc.match_reason}
                                </p>

                                <div className="flex items-center gap-2 text-xs text-purple-300/80">
                                    <TrendingUp className="w-3 h-3" />
                                    <span>{vc.match_reason}</span>
                                </div>
                            </div>
                            
                            {/* Action */}
                            <div className="flex-shrink-0 self-center">
                                <button className="p-2 rounded-full bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white transition-colors">
                                    <ChevronRight className="w-5 h-5" />
                                </button>
                            </div>
                        </div>
                    </motion.div>
                ))}
            </AnimatePresence>
        </div>
    );
}
