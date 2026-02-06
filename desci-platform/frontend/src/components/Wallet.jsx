/**
 * Wallet Component
 * Token Balance & Rewards Interface
 */
import { useState, useEffect } from 'react';
import client from '../api/client';
import { useAuth } from '../contexts/AuthContext';

export default function Wallet() {
    const { user } = useAuth();
    const [balance, setBalance] = useState(null);
    const [rewards, setRewards] = useState(null);
    const [loading, setLoading] = useState(true);

    // Mock address generator (In real app, connect metamask)
    const walletAddress = user?.uid ?\`0x\${user.uid.slice(0, 40).padEnd(40, '0')}\` : null;

    useEffect(() => {
        const fetchData = async () => {
            if (!walletAddress) return;
            try {
                const [balanceRes, rewardsRes] = await Promise.all([
                    client.get(\`/wallet/\${walletAddress}\`),
                    client.get('/reward/amounts')
                ]);
                setBalance(balanceRes.data);
                setRewards(rewardsRes.data);
            } catch (err) {
                console.error('Wallet fetch failed', err);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, [walletAddress]);

    return (
        <div className="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-900 to-pink-800 p-8">
            <div className="max-w-4xl mx-auto">
                <h2 className="text-3xl font-bold text-white mb-8">💰 My DeSci Wallet</h2>

                <div className="grid md:grid-cols-2 gap-6">
                    {/* Balance Card */}
                    <div className="bg-gradient-to-r from-yellow-600/20 to-orange-600/20 backdrop-blur-lg rounded-2xl p-8 border border-yellow-500/30">
                        <h3 className="text-gray-300 font-medium mb-2">Total Balance</h3>
                        <div className="flex items-baseline gap-3">
                            <span className="text-5xl font-bold text-white">
                                {loading ? '...' : parseFloat(balance?.balance || 0).toLocaleString()}
                            </span>
                            <span className="text-xl text-yellow-400 font-bold">DSCI</span>
                        </div>
                        <p className="text-gray-400 text-sm mt-4 font-mono break-all">
                            {walletAddress}
                        </p>
                        {balance?._mock && (
                            <span className="inline-block mt-2 bg-yellow-500/20 text-yellow-200 text-xs px-2 py-1 rounded">
                                TESTNET (Mock)
                            </span>
                        )}
                    </div>

                    {/* Rewards Info */}
                    <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-8 border border-white/20">
                        <h3 className="text-white font-bold mb-4">현재 보상 정책</h3>
                        <div className="space-y-4">
                            <div className="flex justify-between items-center text-gray-300">
                                <span>📄 논문 업로드</span>
                                <span className="text-cyan-400 font-bold">+{rewards?.paper_upload || 100} DSCI</span>
                            </div>
                            <div className="flex justify-between items-center text-gray-300">
                                <span>🔍 피어 리뷰</span>
                                <span className="text-cyan-400 font-bold">+{rewards?.peer_review || 50} DSCI</span>
                            </div>
                            <div className="flex justify-between items-center text-gray-300">
                                <span>💾 데이터 공유</span>
                                <span className="text-cyan-400 font-bold">+{rewards?.data_share || 200} DSCI</span>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Simulated Transaction History (Static for UI Demo) */}
                <div className="mt-8 bg-white/5 rounded-2xl p-6 border border-white/10">
                    <h3 className="text-xl font-bold text-white mb-4">Recent Transactions</h3>
                    <div className="space-y-3">
                        <div className="flex items-center justify-between p-4 bg-white/5 rounded-lg">
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-green-500/20 rounded-lg text-green-400">⬇️</div>
                                <div>
                                    <p className="text-white font-medium">Welcome Bonus</p>
                                    <p className="text-gray-400 text-sm">2026-02-06</p>
                                </div>
                            </div>
                            <span className="text-green-400 font-bold">+100.00 DSCI</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
