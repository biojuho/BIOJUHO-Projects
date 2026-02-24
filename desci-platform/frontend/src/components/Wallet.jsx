/**
 * Wallet Component
 * Token Balance & Rewards Interface
 */
import { useState, useEffect } from 'react';
import client from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';
import Button from './ui/Button';

export default function Wallet() {
    const { walletAddress, connectWallet } = useAuth();
    const { showToast } = useToast();
    const [balance, setBalance] = useState(null);
    const [rewards, setRewards] = useState(null);
    const [transactions, setTransactions] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchData = async () => {
            if (!walletAddress) {
                setLoading(false);
                return;
            }
            try {
                setLoading(true);
                const [balanceRes, rewardsRes, txRes] = await Promise.allSettled([
                    client.get(`/wallet/${walletAddress}`),
                    client.get('/reward/amounts'),
                    client.get(`/transactions/${walletAddress}`)
                ]);
                if (balanceRes.status === 'fulfilled') setBalance(balanceRes.value.data);
                if (rewardsRes.status === 'fulfilled') setRewards(rewardsRes.value.data);
                if (txRes.status === 'fulfilled') setTransactions(txRes.value.data || []);
            } catch (err) {
                console.error('Wallet fetch failed', err);
                showToast("지갑 정보를 불러오는데 실패했습니다.", 'error');
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, [walletAddress, showToast]);

    if (!walletAddress) {
        return (
            <div className="flex items-center justify-center min-h-[60vh]">
                <div className="text-center bg-white/[0.03] backdrop-blur-xl p-10 rounded-2xl border border-white/[0.06]"
                     style={{ boxShadow: '0 16px 48px rgba(0,0,0,0.4)' }}>
                    <h2 className="font-display text-2xl font-bold text-white mb-5">💰 Wallet Connect</h2>
                    <p className="text-white/40 mb-8">
                        보상을 받고 자산을 관리하려면 지갑을 연결하세요.
                    </p>
                    <Button
                        onClick={connectWallet}
                        className="px-8 py-3 text-lg"
                    >
                        🦊 MetaMask / Rabby 연결
                    </Button>
                </div>
            </div>
        );
    }

    return (
        <div className="p-2 sm:p-6">
            <div className="max-w-4xl mx-auto">
                <h2 className="font-display text-2xl font-bold text-white mb-8">💰 My DeSci Wallet</h2>

                <div className="grid md:grid-cols-2 gap-6">
                    {/* Balance Card */}
                    <div className="backdrop-blur-xl rounded-2xl p-8 border gradient-border"
                         style={{ background: 'linear-gradient(135deg, rgba(0,212,170,0.06), rgba(240,192,64,0.06))', boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}>
                        <h3 className="text-white/40 font-medium mb-2">Total Balance</h3>
                        <div className="flex items-baseline gap-3">
                            <span className="font-display text-5xl font-bold text-white">
                                {loading ? '...' : parseFloat(balance?.balance || 0).toLocaleString()}
                            </span>
                            <span className="text-xl text-highlight font-bold font-display">DSCI</span>
                        </div>
                        <p className="text-white/20 text-sm mt-4 font-mono break-all">
                            {walletAddress}
                        </p>
                        {balance?._mock && (
                            <span className="inline-block mt-2 badge-warning text-[10px]">
                                TESTNET (Mock)
                            </span>
                        )}
                    </div>

                    {/* Rewards Info */}
                    <div className="bg-white/[0.03] backdrop-blur-xl rounded-2xl p-8 border border-white/[0.06]"
                         style={{ boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}>
                        <h3 className="font-display text-white font-bold mb-4">현재 보상 정책</h3>
                        <div className="space-y-4">
                            <div className="flex justify-between items-center text-white/50">
                                <span>📄 논문 업로드</span>
                                <span className="text-primary font-bold">+{rewards?.paper_upload || 100} DSCI</span>
                            </div>
                            <div className="flex justify-between items-center text-white/50">
                                <span>🔍 피어 리뷰</span>
                                <span className="text-primary font-bold">+{rewards?.peer_review || 50} DSCI</span>
                            </div>
                            <div className="flex justify-between items-center text-white/50">
                                <span>💾 데이터 공유</span>
                                <span className="text-primary font-bold">+{rewards?.data_share || 200} DSCI</span>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Transaction History */}
                <div className="mt-8 bg-white/[0.02] rounded-2xl p-6 border border-white/[0.04]">
                    <h3 className="font-display text-lg font-bold text-white mb-4">Recent Transactions</h3>
                    <div className="space-y-3">
                        {transactions.length > 0 ? transactions.map((tx, i) => (
                            <div key={tx.id || i} className="flex items-center justify-between p-4 bg-white/[0.02] rounded-xl border border-white/[0.04] hover:bg-white/[0.03] transition-colors">
                                <div className="flex items-center gap-3">
                                    <div className={`p-2 rounded-lg ${tx.amount > 0 ? 'bg-success/10 text-success-light' : 'bg-error/10 text-error-light'}`}>
                                        {tx.amount > 0 ? '⬇️' : '⬆️'}
                                    </div>
                                    <div>
                                        <p className="text-white/80 font-medium">{tx.description}</p>
                                        <p className="text-white/25 text-sm">{tx.timestamp ? new Date(tx.timestamp).toLocaleDateString() : ''}</p>
                                    </div>
                                </div>
                                <span className={`font-bold ${tx.amount > 0 ? 'text-success-light' : 'text-error-light'}`}>
                                    {tx.amount > 0 ? '+' : ''}{parseFloat(tx.amount).toFixed(2)} {tx.token || 'DSCI'}
                                </span>
                            </div>
                        )) : (
                            <div className="text-center py-8 text-white/20 text-sm">
                                거래 내역이 없습니다.
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
