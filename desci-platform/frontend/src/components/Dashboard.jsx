/**
 * Dashboard Component
 * Main authenticated user page
 */
import { useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import client from '../api/client';

export default function Dashboard() {
    const { user, logout } = useAuth();
    const navigate = useNavigate();
    const [backendUser, setBackendUser] = useState(null);
    const [error, setError] = useState('');

    useEffect(() => {
        // Fetch user data from backend
        const fetchUser = async () => {
            try {
                const response = await client.get('/me');
                setBackendUser(response.data);
            } catch (err) {
                console.error('Failed to fetch user:', err);
                setError('백엔드 연결 실패');
            }
        };
        fetchUser();
    }, []);

    const handleLogout = async () => {
        await logout();
        navigate('/login');
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-900 to-pink-800">
            {/* Header */}
            <header className="bg-white/10 backdrop-blur-lg border-b border-white/20">
                <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <span className="text-3xl">🧬</span>
                        <h1 className="text-xl font-bold text-white">DSCI-DecentBio</h1>
                    </div>
                    <div className="flex items-center gap-4">
                        <span className="text-gray-300">
                            {user?.displayName || user?.email}
                        </span>
                        {user?.photoURL && (
                            <img
                                src={user.photoURL}
                                alt="Profile"
                                className="w-10 h-10 rounded-full border-2 border-cyan-400"
                            />
                        )}
                        <button
                            onClick={handleLogout}
                            className="px-4 py-2 bg-white/10 hover:bg-white/20 text-white rounded-lg transition-all"
                        >
                            로그아웃
                        </button>
                    </div>
                </div>
            </header>

            {/* Main Content */}
            <main className="max-w-7xl mx-auto px-4 py-12">
                <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-8 border border-white/20">
                    <h2 className="text-3xl font-bold text-white mb-2">
                        환영합니다! 👋
                    </h2>
                    <p className="text-cyan-400 text-xl mb-8">
                        {user?.displayName || user?.email?.split('@')[0]}님
                    </p>

                    {/* User Info Cards */}
                    <div className="grid md:grid-cols-2 gap-6">
                        {/* Firebase User Info */}
                        <div className="bg-white/5 rounded-xl p-6 border border-white/10">
                            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                                🔥 Firebase 인증 정보
                            </h3>
                            <div className="space-y-2 text-gray-300">
                                <p><span className="text-gray-500">UID:</span> {user?.uid?.slice(0, 20)}...</p>
                                <p><span className="text-gray-500">Email:</span> {user?.email}</p>
                                <p><span className="text-gray-500">Provider:</span> {user?.providerData?.[0]?.providerId}</p>
                            </div>
                        </div>

                        {/* Backend User Info */}
                        <div className="bg-white/5 rounded-xl p-6 border border-white/10">
                            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                                ⚡ 백엔드 연결 상태
                            </h3>
                            {error ? (
                                <p className="text-red-400">{error}</p>
                            ) : backendUser ? (
                                <div className="space-y-2 text-gray-300">
                                    <p><span className="text-gray-500">UID:</span> {backendUser.uid?.slice(0, 20)}...</p>
                                    <p><span className="text-gray-500">Email:</span> {backendUser.email}</p>
                                    <p className="text-green-400">✅ 토큰 검증 성공!</p>
                                </div>
                            ) : (
                                <p className="text-gray-400">로딩 중...</p>
                            )}
                        </div>
                    </div>

                    {/* Features */}
                    <div className="mt-8 p-6 bg-gradient-to-r from-cyan-500/20 to-purple-500/20 rounded-xl border border-cyan-500/30">
                        <h3 className="text-xl font-semibold text-white mb-4">🚀 Features</h3>
                        <div className="grid md:grid-cols-3 gap-4">
                            <a
                                href="/biolinker"
                                className="flex items-center gap-2 text-cyan-300 hover:text-cyan-100 transition-colors p-3 bg-white/5 rounded-lg hover:bg-white/10"
                            >
                                <span>🧬</span> BioLinker 과제 매칭
                            </a>
                            <a
                                href="/upload"
                                className="flex items-center gap-2 text-cyan-300 hover:text-cyan-100 transition-colors p-3 bg-white/5 rounded-lg hover:bg-white/10"
                            >
                                <span>📄</span> 연구 논문 업로드
                            </a>
                            <a
                                href="/mylab"
                                className="flex items-center gap-2 text-purple-300 hover:text-purple-100 transition-colors p-3 bg-white/5 rounded-lg hover:bg-white/10"
                            >
                                <span>🧪</span> 내 연구실 (My Lab)
                            </a>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
}
