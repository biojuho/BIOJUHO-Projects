import { useEffect, useState } from 'react';
import { Activity, ArrowRight, Clock, FileText, Sparkles, TrendingUp } from 'lucide-react';
import { motion } from 'framer-motion';
import { useAuth } from '../contexts/AuthContext';
import { useLocale } from '../contexts/LocaleContext';
import client from '../services/api';
import RecommendationList from './dashboard/RecommendationList';
import VCMatchList from './dashboard/VCMatchList';
import GlassCard from './ui/GlassCard';
import { Badge } from './ui/Badge';

const MotionDiv = motion.div;

export default function Dashboard() {
    const { user, walletAddress } = useAuth();
    const { t } = useLocale();
    const [backendUser, setBackendUser] = useState(null);
    const [backendError, setBackendError] = useState(false);
    const [dashboardData, setDashboardData] = useState({
        paperCount: null,
        vectorCount: null,
        balance: null,
    });

    useEffect(() => {
        const fetchDashboardData = async () => {
            try {
                setBackendError(false);
                const [userRes, papersRes, vectorRes] = await Promise.allSettled([
                    client.get('/me'),
                    client.get('/papers/me'),
                    client.get('/vector/count'),
                ]);

                if (userRes.status === 'fulfilled') {
                    setBackendUser(userRes.value.data);
                } else {
                    setBackendUser(null);
                    setBackendError(true);
                }

                const paperCount = papersRes.status === 'fulfilled' ? papersRes.value.data.length : 0;
                const vectorCount = vectorRes.status === 'fulfilled' ? (vectorRes.value.data.count || 0) : 0;

                let balance = '0';
                if (walletAddress) {
                    try {
                        const walletRes = await client.get(`/wallet/${walletAddress}`);
                        balance = parseFloat(walletRes.data?.balance || 0).toLocaleString();
                    } catch {
                        balance = '0';
                    }
                }

                setDashboardData({
                    paperCount,
                    vectorCount,
                    balance,
                });
            } catch {
                setBackendUser(null);
                setBackendError(true);
            }
        };

        fetchDashboardData();
    }, [walletAddress]);

    const stats = [
        {
            id: 'papersUploaded',
            value: dashboardData.paperCount == null ? '...' : String(dashboardData.paperCount),
            icon: FileText,
            hint: dashboardData.paperCount == null
                ? t('dashboard.statLoading')
                : dashboardData.paperCount > 0
                    ? t('dashboard.statIndexed', { count: dashboardData.paperCount })
                    : t('dashboard.statUploadToStart'),
        },
        {
            id: 'vectorIndex',
            value: dashboardData.vectorCount == null ? '...' : String(dashboardData.vectorCount),
            icon: Activity,
            hint: t('dashboard.statDocuments'),
        },
        { id: 'pendingReviews', value: '0', icon: Clock, hint: t('dashboard.statComingSoon') },
        {
            id: 'tokenBalance',
            value: dashboardData.balance ?? '...',
            icon: TrendingUp,
            hint: 'DSCI',
        },
    ];

    const firstName = user?.displayName?.split(' ')[0] || t('dashboard.researcherFallback');

    const actionCards = [
        { href: '/upload', title: t('dashboard.quickUploadTitle'), body: t('dashboard.quickUploadSubtitle') },
        { href: '/notices', title: t('dashboard.quickGrantTitle'), body: t('dashboard.quickGrantSubtitle') },
        { href: '/vc-portal', title: t('dashboard.quickVcTitle'), body: t('dashboard.quickVcSubtitle') },
        { href: '/biolinker', title: t('dashboard.quickMatchTitle'), body: t('dashboard.quickMatchSubtitle') },
    ];

    return (
        <MotionDiv initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
            <GlassCard className="overflow-hidden p-8">
                <div className="grid gap-6 lg:grid-cols-[1.6fr,1fr]">
                    <div>
                        <p className="clay-chip mb-4">{t('dashboard.overview')}</p>
                        <h1 className="font-display text-4xl font-semibold text-ink sm:text-5xl">
                            {t('dashboard.welcomeBack')},{' '}
                            <span className="text-gradient">{firstName}</span>
                        </h1>
                        <p className="mt-4 max-w-2xl text-base leading-8 text-ink-muted">{t('dashboard.summary')}</p>

                        <div className="mt-6 grid gap-4 md:grid-cols-2">
                            <div className="clay-panel-pressed rounded-[1.8rem] p-5">
                                <Badge variant="default" className="mb-3">{t('dashboard.researcherLane')}</Badge>
                                <p className="text-sm leading-7 text-ink-muted">{t('dashboard.laneResearcherBody')}</p>
                            </div>
                            <div className="clay-panel-pressed rounded-[1.8rem] p-5">
                                <Badge variant="accent" className="mb-3">{t('dashboard.funderLane')}</Badge>
                                <p className="text-sm leading-7 text-ink-muted">{t('dashboard.laneFunderBody')}</p>
                            </div>
                        </div>
                    </div>

                    <div className="clay-panel-pressed rounded-[2rem] p-6">
                        <div className="mb-4 flex items-center justify-between">
                            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-ink-soft">{t('dashboard.activityTitle')}</p>
                            <Badge variant="success">{t('dashboard.networkActive')}</Badge>
                        </div>
                        <div className="space-y-4 text-sm leading-7 text-ink-muted">
                            <div className="rounded-[1.4rem] bg-white/55 p-4">{t('dashboard.activity1')}</div>
                            <div className="rounded-[1.4rem] bg-white/55 p-4">{t('dashboard.activity2')}</div>
                            <div className="rounded-[1.4rem] bg-white/55 p-4">{t('dashboard.activity3')}</div>
                        </div>
                    </div>
                </div>
            </GlassCard>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                {stats.map((stat) => {
                    const Icon = stat.icon;
                    return (
                        <GlassCard key={stat.id} hoverEffect className="p-5">
                            <div className="mb-4 flex items-start justify-between">
                                <div>
                                    <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-ink-soft">{t(`dashboard.${stat.id}`)}</p>
                                    <h3 className="mt-2 font-display text-4xl font-semibold text-ink">{stat.value}</h3>
                                </div>
                                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white text-primary shadow-clay-soft">
                                    <Icon className="h-5 w-5" />
                                </div>
                            </div>
                            <p className="text-sm text-ink-muted">{stat.hint}</p>
                        </GlassCard>
                    );
                })}
            </div>

            <div className="grid gap-6 xl:grid-cols-[1.4fr,1fr]">
                <GlassCard className="p-7">
                    <div className="mb-5 flex items-center justify-between">
                        <h2 className="font-display text-2xl font-semibold text-ink">{t('dashboard.accountStatus')}</h2>
                        <Badge variant={backendError ? 'warning' : 'success'}>
                            {backendError ? t('dashboard.backendConnectionFailed') : t('dashboard.online')}
                        </Badge>
                    </div>
                    <div className="grid gap-4 md:grid-cols-2">
                        <div className="clay-panel-pressed rounded-[1.8rem] p-5">
                            <p className="mb-4 text-[11px] font-bold uppercase tracking-[0.18em] text-ink-soft">{t('dashboard.identity')}</p>
                            <div className="space-y-3 text-sm text-ink-muted">
                                <p className="flex justify-between gap-3"><span>{t('dashboard.email')}</span><span className="font-semibold text-ink">{user?.email}</span></p>
                                <p className="flex justify-between gap-3"><span>{t('dashboard.provider')}</span><span className="font-semibold text-ink">{user?.providerData?.[0]?.providerId || 'email'}</span></p>
                                <p className="flex justify-between gap-3"><span>{t('dashboard.uid')}</span><span className="font-mono text-ink">{user?.uid?.slice(0, 8)}...</span></p>
                            </div>
                        </div>
                        <div className="clay-panel-pressed rounded-[1.8rem] p-5">
                            <p className="mb-4 text-[11px] font-bold uppercase tracking-[0.18em] text-ink-soft">{t('dashboard.systemStatus')}</p>
                            <div className="space-y-3 text-sm text-ink-muted">
                                <p className="flex justify-between gap-3"><span>{t('dashboard.node')}</span><span className="font-semibold text-ink">{backendError ? t('dashboard.offline') : t('dashboard.online')}</span></p>
                                <p className="flex justify-between gap-3"><span>{t('dashboard.role')}</span><span className="font-semibold text-ink">{t('dashboard.rolePrincipalInvestigator')}</span></p>
                                <p className="flex justify-between gap-3"><span>{t('dashboard.sync')}</span><span className="font-semibold text-ink">{backendUser ? t('dashboard.automated') : t('dashboard.statLoading')}</span></p>
                            </div>
                        </div>
                    </div>
                </GlassCard>

                <GlassCard className="p-7">
                    <h2 className="mb-5 font-display text-2xl font-semibold text-ink">{t('dashboard.quickActions')}</h2>
                    <div className="space-y-3">
                        {actionCards.map((action) => (
                            <a key={action.href} href={action.href} className="clay-panel-pressed flex items-center justify-between rounded-[1.6rem] px-5 py-4 transition-all hover:-translate-y-1">
                                <div>
                                    <p className="text-sm font-semibold text-ink">{action.title}</p>
                                    <p className="mt-1 text-sm text-ink-muted">{action.body}</p>
                                </div>
                                <ArrowRight className="h-4 w-4 text-primary" />
                            </a>
                        ))}
                    </div>
                </GlassCard>
            </div>

            <div className="grid gap-6 xl:grid-cols-2">
                <GlassCard className="p-7">
                    <div className="mb-5 flex items-center justify-between">
                        <h2 className="font-display text-2xl font-semibold text-ink">{t('dashboard.strategicPartners')}</h2>
                        <Badge variant="accent">{t('dashboard.beta')}</Badge>
                    </div>
                    <VCMatchList />
                </GlassCard>

                <GlassCard className="p-7">
                    <div className="mb-5 flex items-center justify-between">
                        <h2 className="font-display text-2xl font-semibold text-ink">{t('layout.biolinker')}</h2>
                        <Badge variant="default">AI</Badge>
                    </div>
                    <RecommendationList />
                </GlassCard>
            </div>
        </MotionDiv>
    );
}
