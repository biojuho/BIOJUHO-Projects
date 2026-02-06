/**
 * My Lab Component
 * Research Dashboard for managing papers and rewards
 */
import { useState, useEffect } from 'react';
import client from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { Link } from 'react-router-dom';

export default function MyLab() {
    const { user } = useAuth();
    const [papers, setPapers] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchPapers = async () => {
            try {
                // In a real app, we would pass the user ID or token
                const response = await client.get('/papers/me');
                setPapers(response.data);
            } catch (err) {
                console.error('Failed to fetch papers:', err);
            } finally {
                setLoading(false);
            }
        };
        fetchPapers();
    }, []);

    return (
        <div className="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-900 to-pink-800 p-8">
            <div className="max-w-6xl mx-auto">
                {/* Header */}
                <div className="flex justify-between items-center mb-8">
                    <div>
                        <h2 className="text-3xl font-bold text-white flex items-center gap-3">
                            🧪 My Lab
                        </h2>
                        <p className="text-gray-300 mt-2">
                            {user?.displayName}님의 연구 아카이브
                        </p>
                    </div>
                    <Link
                        to="/upload"
                        className="px-6 py-3 bg-gradient-to-r from-cyan-500 to-blue-500 rounded-xl text-white font-bold hover:opacity-90 transition-all flex items-center gap-2"
                    >
                        <span>📤</span> 새 논문 등록
                    </Link>
                </div>

                {/* Stats Overview */}
                <div className="grid md:grid-cols-3 gap-6 mb-10">
                    <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 border border-white/20">
                        <h3 className="text-gray-400 text-sm font-medium uppercase">Total Research</h3>
                        <p className="text-4xl font-bold text-white mt-1">{papers.length}</p>
                    </div>
                    <div className="bg-gradient-to-br from-yellow-500/20 to-orange-500/20 backdrop-blur-lg rounded-2xl p-6 border border-yellow-500/30">
                        <h3 className="text-yellow-200 text-sm font-medium uppercase">Pending Rewards</h3>
                        <p className="text-4xl font-bold text-yellow-400 mt-1">100.0 DSCI</p>
                    </div>
                    <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 border border-white/20">
                        <h3 className="text-gray-400 text-sm font-medium uppercase">Impact Factor</h3>
                        <p className="text-4xl font-bold text-cyan-400 mt-1">Mock</p>
                    </div>
                </div>

                {/* Paper List */}
                <h3 className="text-xl font-bold text-white mb-6">📂 내 논문 목록</h3>

                {loading ? (
                    <div className="text-center py-20">
                        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-cyan-400 mx-auto mb-4"></div>
                        <p className="text-gray-400">연구 데이터를 불러오는 중...</p>
                    </div>
                ) : papers.length > 0 ? (
                    <div className="grid gap-6">
                        {papers.map((paper) => (
                            <div key={paper.id} className="bg-white/5 hover:bg-white/10 transition-colors rounded-xl p-6 border border-white/10 relative overflow-hidden group">
                                <div className="absolute top-0 right-0 p-4 opacity-50 group-hover:opacity-100 transition-opacity">
                                    {paper.reward_claimed ? (
                                        <span className="bg-green-500/20 text-green-400 text-xs px-3 py-1 rounded-full font-bold">
                                            보상 완료 ✅
                                        </span>
                                    ) : (
                                        <span className="bg-yellow-500/20 text-yellow-400 text-xs px-3 py-1 rounded-full font-bold">
                                            심사 중 ⏳
                                        </span>
                                    )}
                                </div>

                                <h4 className="text-xl font-bold text-white mb-2">{paper.title}</h4>
                                <p className="text-gray-400 text-sm line-clamp-2 mb-4">
                                    {paper.abstract}
                                </p>

                                <div className="flex items-center gap-4 text-sm">
                                    <div className="flex items-center gap-2 text-cyan-300 bg-cyan-900/30 px-3 py-1 rounded-lg">
                                        <span>🔗</span>
                                        <span className="font-mono">{paper.cid.slice(0, 10)}...</span>
                                    </div>
                                    <span className="text-gray-500">
                                        {new Date(paper.uploaded_at).toLocaleDateString()}
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="text-center py-20 bg-white/5 rounded-2xl border border-dashed border-white/20">
                        <p className="text-gray-400 mb-4">등록된 연구 논문이 없습니다.</p>
                        <Link to="/upload" className="text-cyan-400 underline hover:text-cyan-300">
                            지금 첫 번째 연구를 등록해보세요!
                        </Link>
                    </div>
                )}
            </div>
        </div>
    );
}
