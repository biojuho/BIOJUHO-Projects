import { useEffect, useState } from 'react';
import { WalletMinimal } from 'lucide-react';
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
            <div className="glass-card mx-auto max-w-2xl p-10 text-center">
                <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-white text-primary shadow-clay-soft">
                    <WalletMinimal className="h-10 w-10" />
                </div>
                <h2 className="font-display text-3xl font-semibold text-ink">{t('wallet.connectTitle')}</h2>
                <p className="mx-auto mt-3 max-w-xl text-sm leading-7 text-ink-muted">{t('wallet.connectDescription')}</p>
                <Button onClick={connectWallet} size="lg" className="mt-6 justify-center text-white">
                    {t('wallet.connectButton')}
                </Button>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <Card glass className="p-7">
                <CardContent className="p-0">
                    <h1 className="font-display text-4xl font-semibold text-ink">{t('wallet.pageTitle')}</h1>
                    <p className="mt-3 text-sm leading-7 text-ink-muted">{t('wallet.rewardsCaption')}</p>
                </CardContent>
            </Card>

            <div className="grid gap-6 md:grid-cols-2">
                <Card glass className="p-8">
                    <CardContent className="p-0">
                        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-ink-soft">{t('wallet.totalBalance')}</p>
                        <div className="mt-4 flex items-baseline gap-3">
                            <span className="font-display text-5xl font-semibold text-ink">
                                {loading ? '...' : parseFloat(balance?.balance || 0).toLocaleString()}
                            </span>
                            <span className="text-xl font-semibold text-primary">DSCI</span>
                        </div>
                        <p className="mt-4 break-all font-mono text-xs text-ink-muted">{walletAddress}</p>
                        {balance?._mock && (
                            <Badge variant="warning" className="mt-3">{t('wallet.testnetMock')}</Badge>
                        )}
                    </CardContent>
                </Card>

                <Card glass className="p-8">
                    <CardContent className="p-0">
                        <h2 className="mb-4 font-display text-2xl font-semibold text-ink">{t('wallet.rewardPolicy')}</h2>
                        <div className="space-y-4 text-sm text-ink-muted">
                            <div className="flex justify-between gap-3"><span>{t('wallet.rewardPaperUpload')}</span><span className="font-semibold text-primary">+{rewards?.paper_upload || 100} DSCI</span></div>
                            <div className="flex justify-between gap-3"><span>{t('wallet.rewardPeerReview')}</span><span className="font-semibold text-primary">+{rewards?.peer_review || 50} DSCI</span></div>
                            <div className="flex justify-between gap-3"><span>{t('wallet.rewardDataShare')}</span><span className="font-semibold text-primary">+{rewards?.data_share || 200} DSCI</span></div>
                        </div>
                    </CardContent>
                </Card>
            </div>

            <Card glass className="p-7">
                <CardContent className="p-0">
                    <h2 className="mb-5 font-display text-2xl font-semibold text-ink">{t('wallet.recentTransactions')}</h2>
                    <div className="space-y-3">
                        {transactions.length > 0 ? transactions.map((tx, index) => (
                            <div key={tx.id || index} className="clay-panel-pressed flex items-center justify-between gap-4 rounded-[1.6rem] p-4">
                                <div>
                                    <p className="font-semibold text-ink">{tx.description}</p>
                                    <p className="text-xs text-ink-muted">{tx.timestamp ? new Date(tx.timestamp).toLocaleDateString() : ''}</p>
                                </div>
                                <span className={tx.amount > 0 ? 'font-semibold text-success' : 'font-semibold text-error-dark'}>
                                    {tx.amount > 0 ? '+' : ''}{parseFloat(tx.amount).toFixed(2)} {tx.token || 'DSCI'}
                                </span>
                            </div>
                        )) : (
                            <div className="text-sm text-ink-muted">{t('wallet.noTransactions')}</div>
                        )}
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
