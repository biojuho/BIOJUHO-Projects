/**
 * Wallet Component
 * Token Balance & Rewards Interface
 */
import { useState, useEffect } from 'react';
import client from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';
import { useLocale } from '../contexts/LocaleContext';
import Button from './ui/Button';
import { Card, CardContent } from './ui/Card';
import { Badge } from './ui/Badge';

export default function Wallet() {
    const { walletAddress, connectWallet } = useAuth();
    const { showToast } = useToast();
    const { t } = useLocale();
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
                    client.get(`/transactions/${walletAddress}`),
                ]);
                if (balanceRes.status === 'fulfilled') setBalance(balanceRes.value.data);
                if (rewardsRes.status === 'fulfilled') setRewards(rewardsRes.value.data);
                if (txRes.status === 'fulfilled') setTransactions(txRes.value.data || []);
            } catch (err) {
                console.error('Wallet fetch failed', err);
                showToast({ key: 'wallet.fetchFailed' }, 'error');
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, [walletAddress, showToast]);

    if (!walletAddress) {
        return (
            <div className="flex items-center justify-center min-h-[60vh]">
                <Card glass className="p-10 text-center">
                    <CardContent>
                        <h2 className="font-display text-2xl font-bold text-white mb-5">{t('wallet.connectTitle')}</h2>
                        <p className="text-white/40 mb-8">
                            {t('wallet.connectDescription')}
                        </p>
                        <Button
                            onClick={connectWallet}
                            className="px-8 py-3 text-lg"
                        >
                            {t('wallet.connectButton')}
                        </Button>
                    </CardContent>
                </Card>
            </div>
        );
    }

    return (
        <div className="p-2 sm:p-6">
            <div className="max-w-4xl mx-auto">
                <h2 className="font-display text-2xl font-bold text-white mb-8">{t('wallet.pageTitle')}</h2>

                <div className="grid md:grid-cols-2 gap-6">
                    <div
                        className="backdrop-blur-xl rounded-2xl p-8 border gradient-border"
                        style={{ background: 'linear-gradient(135deg, rgba(0,212,170,0.06), rgba(240,192,64,0.06))', boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}
                    >
                        <h3 className="text-white/40 font-medium mb-2">{t('wallet.totalBalance')}</h3>
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
                            <Badge variant="warning" className="mt-2 text-[10px]">
                                {t('wallet.testnetMock')}
                            </Badge>
                        )}
                    </div>

                    <Card glass className="p-8">
                        <CardContent>
                            <h3 className="font-display text-white font-bold mb-4">{t('wallet.rewardPolicy')}</h3>
                            <div className="space-y-4">
                                <div className="flex justify-between items-center text-white/50">
                                    <span>{t('wallet.rewardPaperUpload')}</span>
                                    <span className="text-primary font-bold">+{rewards?.paper_upload || 100} DSCI</span>
                                </div>
                                <div className="flex justify-between items-center text-white/50">
                                    <span>{t('wallet.rewardPeerReview')}</span>
                                    <span className="text-primary font-bold">+{rewards?.peer_review || 50} DSCI</span>
                                </div>
                                <div className="flex justify-between items-center text-white/50">
                                    <span>{t('wallet.rewardDataShare')}</span>
                                    <span className="text-primary font-bold">+{rewards?.data_share || 200} DSCI</span>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </div>

                <Card className="mt-8 bg-white/[0.02] p-6">
                    <CardContent>
                        <h3 className="font-display text-lg font-bold text-white mb-4">{t('wallet.recentTransactions')}</h3>
                        <div className="space-y-3">
                            {transactions.length > 0 ? transactions.map((tx, index) => (
                                <div key={tx.id || index} className="flex items-center justify-between p-4 bg-white/[0.02] rounded-xl border border-white/[0.04] hover:bg-white/[0.03] transition-colors">
                                    <div className="flex items-center gap-3">
                                        <div className={`p-2 rounded-lg ${tx.amount > 0 ? 'bg-success/10 text-success-light' : 'bg-error/10 text-error-light'}`}>
                                            {tx.amount > 0 ? '↗' : '↘'}
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
                                    {t('wallet.noTransactions')}
                                </div>
                            )}
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
