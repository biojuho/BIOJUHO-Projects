/**
 * Dashboard Component
 * Main authenticated user page
 * Design: Bioluminescent Neural Network
 */
import { useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import client from '../services/api';
import RecommendationList from './dashboard/RecommendationList';
import VCMatchList from './dashboard/VCMatchList';
import GlassCard from './ui/GlassCard';
import {
    FileText,
    Activity,
    Clock,
    TrendingUp,
    ShieldCheck,
    AlertCircle,
    Building2,
    Upload,
    Search,
    ArrowRight,
    Zap
} from 'lucide-react';
import { motion } from 'framer-motion';

const MotionDiv = motion.div;

export default function Dashboard() {
    const { user, walletAddress } = useAuth();
    const [backendUser, setBackendUser] = useState(null);
    const [error, setError] = useState('');
    const [stats, setStats] = useState([
        { label: 'Papers Uploaded', value: '...', icon: FileText, color: 'text-primary', bgColor: 'from-primary/10 to-primary/5', trend: 'Loading' },
        { label: 'Vector Index', value: '...', icon: Activity, color: 'text-success-light', bgColor: 'from-success/10 to-success/5', trend: 'Documents' },
        { label: 'Pending Reviews', value: '0', icon: Clock, color: 'text-highlight', bgColor: 'from-highlight/10 to-highlight/5', trend: 'Coming soon' },
        { label: 'Token Balance', value: '...', icon: TrendingUp, color: 'text-accent-light', bgColor: 'from-accent/10 to-accent/5', trend: 'DSCI' },
    ]);

    useEffect(() => {
        const fetchDashboardData = async () => {
            try {
                const [userRes, papersRes, vectorRes] = await Promise.allSettled([
                    client.get('/me'),
                    client.get('/papers/me'),
                    client.get('/vector/count'),
                ]);

                if (userRes.status === 'fulfilled') setBackendUser(userRes.value.data);
                else setError('Backend connection failed');

                const paperCount = papersRes.status === 'fulfilled' ? papersRes.value.data.length : 0;
                const vectorCount = vectorRes.status === 'fulfilled' ? (vectorRes.value.data.count || 0) : 0;

                let balance = '0';
                if (walletAddress) {
                    try {
                        const balRes = await client.get(`/wallet/${walletAddress}`);
                        balance = parseFloat(balRes.data?.balance || 0).toLocaleString();
                    } catch { /* use default */ }
                }

                setStats(prev => prev.map(s => {
                    if (s.label === 'Papers Uploaded') return { ...s, value: String(paperCount), trend: paperCount > 0 ? `${paperCount} indexed` : 'Upload to start' };
                    if (s.label === 'Vector Index') return { ...s, value: String(vectorCount), trend: 'Documents indexed' };
                    if (s.label === 'Token Balance') return { ...s, value: balance, trend: 'DSCI' };
                    return s;
                }));
            } catch (err) {
                console.error('Dashboard data fetch failed:', err);
                setError('Backend connection failed');
            }
        };
        fetchDashboardData();
    }, [walletAddress]);

    const container = {
        hidden: { opacity: 0 },
        show: {
            opacity: 1,
            transition: {
                staggerChildren: 0.08,
                delayChildren: 0.1,
            }
        }
    };

    const item = {
        hidden: { opacity: 0, y: 20 },
        show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] } }
    };

    return (
        <MotionDiv
            className="space-y-8"
            variants={container}
            initial="hidden"
            animate="show"
        >
            {/* Header Section */}
            <MotionDiv variants={item} className="flex flex-col md:flex-row md:items-end justify-between gap-4">
                <div>
                    <p className="text-xs text-white/30 uppercase tracking-[0.2em] font-medium mb-2">Overview</p>
                    <h1 className="font-display text-3xl sm:text-4xl font-bold text-white tracking-tight">
                        Welcome back
                        <span className="text-gradient block sm:inline">, {user?.displayName?.split(' ')[0] || 'Researcher'}</span>
                    </h1>
                </div>
                <div className="flex items-center gap-3">
                    <span className="px-3 py-1.5 rounded-full text-xs font-medium flex items-center gap-2 border border-primary/20 text-primary bg-primary/[0.06]">
                        <span className="w-1.5 h-1.5 bg-primary rounded-full animate-pulse"></span>
                        Network Active
                    </span>
                </div>
            </MotionDiv>

            {/* KPI Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
                {stats.map((stat, index) => {
                    const Icon = stat.icon;
                    return (
                        <GlassCard
                            key={index}
                            delay={0.1 + index * 0.06}
                            hoverEffect={true}
                            className="flex flex-col justify-between p-5"
                        >
                            <div className="flex items-start justify-between mb-4">
                                <div>
                                    <p className="text-xs font-medium text-white/30 uppercase tracking-wider">{stat.label}</p>
                                    <h3 className="font-display text-3xl font-bold text-white mt-1.5 tracking-tight">{stat.value}</h3>
                                </div>
                                <div className={`p-2.5 rounded-xl bg-gradient-to-br ${stat.bgColor} ${stat.color}`}>
                                    <Icon className="w-5 h-5" />
                                </div>
                            </div>
                            <div className="neural-line mb-3" />
                            <div className="flex items-center gap-1.5 text-xs text-white/25 font-medium">
                                <Zap className={`w-3 h-3 ${stat.color}`} />
                                <span className={stat.color}>{stat.trend}</span>
                            </div>
                        </GlassCard>
                    );
                })}
            </div>

            {/* Main Content Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

                {/* Account Status */}
                <GlassCard className="lg:col-span-2 p-7" delay={0.4}>
                    <h3 className="font-display text-lg font-semibold text-white mb-5 flex items-center gap-2.5">
                        <div className="p-1.5 rounded-lg bg-primary/10">
                            <ShieldCheck className="w-4 h-4 text-primary" />
                        </div>
                        Account Status
                    </h3>

                    <div className="grid md:grid-cols-2 gap-5">
                        <div className="bg-white/[0.02] rounded-xl p-5 border border-white/[0.04] hover:border-white/[0.08] transition-colors">
                            <h4 className="text-[11px] font-medium text-white/25 mb-4 uppercase tracking-[0.15em]">Identity</h4>
                            <div className="space-y-3">
                                <p className="flex justify-between text-sm"><span className="text-white/30">Email</span> <span className="text-white/80 font-medium">{user?.email}</span></p>
                                <p className="flex justify-between text-sm"><span className="text-white/30">Provider</span> <span className="capitalize badge-primary text-xs px-2 py-0.5 rounded-md">{user?.providerData?.[0]?.providerId}</span></p>
                                <p className="flex justify-between text-sm"><span className="text-white/30">UID</span> <span className="text-white/40 font-mono text-xs">{user?.uid?.slice(0, 8)}...</span></p>
                            </div>
                        </div>

                        <div className="bg-white/[0.02] rounded-xl p-5 border border-white/[0.04] hover:border-white/[0.08] transition-colors">
                            <h4 className="text-[11px] font-medium text-white/25 mb-4 uppercase tracking-[0.15em]">System Status</h4>
                            {error ? (
                                <div className="flex items-center gap-3 text-error-light bg-error/[0.08] p-3 rounded-lg border border-error/10">
                                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                                    <span className="text-sm font-medium">{error}</span>
                                </div>
                            ) : backendUser ? (
                                <div className="space-y-3">
                                    <p className="flex justify-between text-sm"><span className="text-white/30">Node</span> <span className="text-primary font-medium flex items-center gap-1.5"><span className="w-1.5 h-1.5 bg-primary rounded-full"></span> Online</span></p>
                                    <p className="flex justify-between text-sm"><span className="text-white/30">Role</span> <span className="text-white/80 font-medium">Principal Investigator</span></p>
                                    <p className="flex justify-between text-sm"><span className="text-white/30">Sync</span> <span className="text-white/40 font-mono text-xs">Automated</span></p>
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    <div className="h-4 skeleton rounded w-3/4"></div>
                                    <div className="h-4 skeleton rounded w-full"></div>
                                    <div className="h-4 skeleton rounded w-1/2"></div>
                                </div>
                            )}
                        </div>
                    </div>
                </GlassCard>

                {/* Quick Actions */}
                <GlassCard className="p-7" delay={0.5}>
                    <h3 className="font-display text-lg font-semibold text-white mb-5">Quick Actions</h3>
                    <div className="space-y-3">
                        <a href="/upload" className="group block w-full text-left px-4 py-3.5 bg-white/[0.02] hover:bg-white/[0.05] rounded-xl transition-all duration-300 border border-white/[0.04] hover:border-primary/20">
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-primary/10 text-primary rounded-lg group-hover:bg-primary group-hover:text-white transition-all duration-300">
                                    <Upload className="w-4 h-4" />
                                </div>
                                <div className="flex-1">
                                    <span className="block text-sm font-medium text-white/80 group-hover:text-white transition-colors">Upload Paper</span>
                                    <span className="text-[11px] text-white/25">Mint IP-NFT</span>
                                </div>
                                <ArrowRight className="w-3.5 h-3.5 text-white/10 group-hover:text-primary group-hover:translate-x-1 transition-all" />
                            </div>
                        </a>
                        <a href="/biolinker" className="group block w-full text-left px-4 py-3.5 bg-white/[0.02] hover:bg-white/[0.05] rounded-xl transition-all duration-300 border border-white/[0.04] hover:border-accent/20">
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-accent/10 text-accent-light rounded-lg group-hover:bg-accent group-hover:text-white transition-all duration-300">
                                    <Search className="w-4 h-4" />
                                </div>
                                <div className="flex-1">
                                    <span className="block text-sm font-medium text-white/80 group-hover:text-white transition-colors">Find Grants</span>
                                    <span className="text-[11px] text-white/25">AI Matching</span>
                                </div>
                                <ArrowRight className="w-3.5 h-3.5 text-white/10 group-hover:text-accent-light group-hover:translate-x-1 transition-all" />
                            </div>
                        </a>
                        <a href="/vc-portal" className="group block w-full text-left px-4 py-3.5 rounded-xl transition-all duration-300 border border-accent/10 hover:border-accent/25 gradient-border"
                           style={{ background: 'linear-gradient(135deg, rgba(99,102,241,0.04), rgba(0,212,170,0.04))' }}>
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <div className="p-2 bg-highlight/10 text-highlight rounded-lg group-hover:bg-highlight group-hover:text-surface transition-all duration-300">
                                        <Building2 className="w-4 h-4" />
                                    </div>
                                    <div>
                                        <span className="block text-sm font-medium text-white/80 group-hover:text-white transition-colors">VC Portal</span>
                                        <span className="text-[11px] text-white/25">Strategic Partners</span>
                                    </div>
                                </div>
                                <ArrowRight className="w-3.5 h-3.5 text-white/10 group-hover:text-highlight group-hover:translate-x-1 transition-all" />
                            </div>
                        </a>
                    </div>
                </GlassCard>
            </div>

            {/* VC Matches - Full Width Section */}
            <GlassCard className="p-7" delay={0.6}>
                <h3 className="font-display text-lg font-semibold text-white mb-5 flex items-center gap-2.5">
                    <div className="p-1.5 rounded-lg bg-accent/10">
                        <Building2 className="w-4 h-4 text-accent-light" />
                    </div>
                    Strategic VC Partners
                    <span className="badge-primary text-[10px] ml-1">Beta</span>
                </h3>
                <VCMatchList />
            </GlassCard>
        </MotionDiv>
    );
}
