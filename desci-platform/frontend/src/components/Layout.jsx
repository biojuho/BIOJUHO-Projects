import { Link, useLocation } from 'react-router-dom';
import { useState, useMemo } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
    LayoutDashboard,
    Sparkles,
    Upload,
    FlaskConical,
    Wallet,
    LogOut,
    Menu,
    X,
    Building2,
    Bell,
    ChevronRight,
    Newspaper,
    Cpu,
    MessageSquare,
    Library,
    Scale,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useLocale } from '../contexts/LocaleContext';
import { useToast } from '../contexts/ToastContext';
import Footer from './Footer';
import LocaleToggle from './ui/LocaleToggle';

const MotionDiv = motion.div;

function formatAddress(address) {
    if (!address) return '';
    return `${address.slice(0, 6)}...${address.slice(-4)}`;
}

export default function Layout({ children }) {
    const { user, logout, walletAddress, connectWallet } = useAuth();
    const { t } = useLocale();
    const { showToast } = useToast();
    const location = useLocation();
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
    const [notificationsOpen, setNotificationsOpen] = useState(false);

    const notifications = useMemo(() => ([
        { id: 1, title: t('layout.notificationGrantTitle'), desc: t('layout.notificationGrantDesc'), time: t('layout.timeNow') },
        { id: 2, title: t('layout.notificationReviewTitle'), desc: t('layout.notificationReviewDesc'), time: t('layout.timeHourAgo') },
        { id: 3, title: t('layout.notificationAirdropTitle'), desc: t('layout.notificationAirdropDesc'), time: t('layout.timeDaysAgo', { count: 1 }) },
    ]), [t]);

    const navGroups = [
        {
            title: t('layout.market'),
            items: [
                { name: t('layout.dashboard'), href: '/dashboard', icon: LayoutDashboard },
                { name: t('layout.notices'), href: '/notices', icon: Newspaper },
                { name: t('layout.vcPortal'), href: '/vc-portal', icon: Building2 },
                { name: t('layout.biolinker'), href: '/biolinker', icon: Sparkles },
            ],
        },
        {
            title: t('layout.workspace'),
            items: [
                { name: t('layout.paperUpload'), href: '/upload', icon: Upload },
                { name: t('layout.myLab'), href: '/mylab', icon: FlaskConical },
                { name: t('layout.aiLab'), href: '/ai-lab', icon: Cpu },
                { name: t('layout.peerReview'), href: '/peer-review', icon: MessageSquare },
            ],
        },
        {
            title: t('layout.trust'),
            items: [
                { name: t('layout.wallet'), href: '/wallet', icon: Wallet },
                { name: t('layout.assets'), href: '/assets', icon: Library },
                { name: t('layout.governance'), href: '/governance', icon: Scale },
            ],
        },
    ];

    const handleConnectWallet = async () => {
        const result = await connectWallet();
        if (result.success) {
            showToast({ key: 'layout.walletConnectedDesc', values: { address: formatAddress(result.address) } }, 'success');
            return;
        }

        alert(result.error || t('layout.walletConnectFailed'));
    };

    return (
        <div className="relative min-h-screen">
            <div className="ambient-bg" aria-hidden="true" />
            <div className="pointer-events-none fixed inset-0 overflow-hidden" aria-hidden="true">
                <div className="hero-orb hero-orb-mint left-[6%] top-[10%] h-40 w-40 animate-float" />
                <div className="hero-orb hero-orb-sky right-[10%] top-[8%] h-48 w-48 animate-float" />
                <div className="hero-orb hero-orb-peach bottom-[12%] left-[28%] h-36 w-36 animate-float" />
            </div>

            <div className="relative z-10 flex min-h-screen gap-5 px-3 pb-4 pt-3 lg:px-5 lg:pt-5">
                <AnimatePresence>
                    {(isMobileMenuOpen || typeof window === 'undefined') && (
                        <MotionDiv
                            initial={{ opacity: 0 }}
                            animate={{ opacity: isMobileMenuOpen ? 1 : 0 }}
                            exit={{ opacity: 0 }}
                            className={`fixed inset-0 z-30 bg-[#d9cdbf]/35 backdrop-blur-sm lg:hidden ${isMobileMenuOpen ? 'block' : 'hidden'}`}
                            onClick={() => setIsMobileMenuOpen(false)}
                        />
                    )}
                </AnimatePresence>

                <aside
                    className={[
                        'glass-card fixed inset-y-3 left-3 z-40 flex w-[300px] flex-col p-5 lg:static lg:inset-auto lg:z-10 lg:w-[290px]',
                        isMobileMenuOpen ? 'translate-x-0' : '-translate-x-[120%] lg:translate-x-0',
                        'transition-transform duration-300 ease-smooth',
                    ].join(' ')}
                >
                    <div className="mb-6 flex items-center justify-between lg:hidden">
                        <span className="font-display text-xl font-semibold text-ink">DSCI</span>
                        <button className="clay-button h-10 w-10 !px-0" onClick={() => setIsMobileMenuOpen(false)} aria-label={t('layout.closeMenu')}>
                            <X className="h-4 w-4" />
                        </button>
                    </div>

                    <Link to="/dashboard" className="mb-8 block">
                        <div className="flex items-start gap-4">
                            <div className="flex h-14 w-14 items-center justify-center rounded-[1.6rem] bg-gradient-to-br from-primary to-accent text-white shadow-clay-soft">
                                <Sparkles className="h-6 w-6" />
                            </div>
                            <div>
                                <h1 className="font-display text-[2rem] font-semibold leading-none text-ink">DSCI</h1>
                                <p className="mt-2 text-sm leading-6 text-ink-muted">{t('layout.brandSubtitle')}</p>
                            </div>
                        </div>
                    </Link>

                    <div className="mb-6 flex items-center gap-3 rounded-[1.7rem] bg-white/65 p-4 shadow-clay-soft">
                        {user?.photoURL ? (
                            <img src={user.photoURL} alt={user?.displayName || 'user'} className="h-12 w-12 rounded-[1.2rem] object-cover" />
                        ) : (
                            <div className="flex h-12 w-12 items-center justify-center rounded-[1.2rem] bg-gradient-to-br from-primary to-accent text-white">
                                {(user?.displayName || user?.email || 'U').slice(0, 1).toUpperCase()}
                            </div>
                        )}
                        <div className="min-w-0">
                            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-ink-soft">{t('layout.signedInAs')}</p>
                            <p className="truncate text-sm font-semibold text-ink">{user?.displayName || t('layout.researcher')}</p>
                            <p className="truncate text-xs text-ink-muted">{user?.email}</p>
                        </div>
                    </div>

                    <div className="scrollbar-hide flex-1 overflow-y-auto pr-1">
                        {navGroups.map((group) => (
                            <div key={group.title} className="mb-6">
                                <p className="mb-3 px-2 text-[11px] font-bold uppercase tracking-[0.2em] text-ink-soft">
                                    {group.title}
                                </p>
                                <div className="space-y-2">
                                    {group.items.map((item) => {
                                        const Icon = item.icon;
                                        const active = location.pathname === item.href;
                                        return (
                                            <Link
                                                key={item.href}
                                                to={item.href}
                                                onClick={() => setIsMobileMenuOpen(false)}
                                                className={[
                                                    'flex items-center justify-between rounded-[1.4rem] px-4 py-3 transition-all duration-300',
                                                    active
                                                        ? 'bg-white text-ink shadow-clay-soft'
                                                        : 'text-ink-muted hover:bg-white/70 hover:text-ink',
                                                ].join(' ')}
                                            >
                                                <span className="flex items-center gap-3">
                                                    <span className={`flex h-10 w-10 items-center justify-center rounded-full ${active ? 'bg-primary/15 text-primary' : 'bg-surface-overlay/80 text-ink-soft'}`}>
                                                        <Icon className="h-4 w-4" />
                                                    </span>
                                                    <span className="text-sm font-semibold">{item.name}</span>
                                                </span>
                                                <ChevronRight className={`h-4 w-4 ${active ? 'text-primary' : 'text-ink-soft'}`} />
                                            </Link>
                                        );
                                    })}
                                </div>
                            </div>
                        ))}
                    </div>

                    <div className="mt-4 space-y-3">
                        <LocaleToggle />
                        <button onClick={logout} className="clay-button w-full justify-center">
                            <LogOut className="h-4 w-4" />
                            {t('layout.signOut')}
                        </button>
                    </div>
                </aside>

                <main className="flex min-h-screen flex-1 flex-col lg:min-w-0">
                    <div className="glass-card mb-5 flex items-center justify-between gap-3 px-4 py-4 lg:px-6">
                        <div className="flex items-center gap-3">
                            <button className="clay-button h-11 w-11 !px-0 lg:hidden" onClick={() => setIsMobileMenuOpen(true)} aria-label={t('layout.openMenu')}>
                                <Menu className="h-4 w-4" />
                            </button>
                            <div>
                                <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-ink-soft">{t('layout.headerTitle')}</p>
                                <h2 className="font-display text-2xl font-semibold text-ink">{t('layout.headerSubtitle')}</h2>
                            </div>
                        </div>
                        <div className="flex items-center gap-3">
                            <div className="hidden lg:block">
                                <LocaleToggle />
                            </div>
                            <div className="relative">
                                <button
                                    type="button"
                                    onClick={() => setNotificationsOpen((open) => !open)}
                                    className="clay-button h-11 w-11 !px-0"
                                    aria-label={t('layout.notifications')}
                                >
                                    <Bell className="h-4 w-4" />
                                </button>
                                <AnimatePresence>
                                    {notificationsOpen && (
                                        <MotionDiv
                                            initial={{ opacity: 0, y: 10, scale: 0.97 }}
                                            animate={{ opacity: 1, y: 0, scale: 1 }}
                                            exit={{ opacity: 0, y: 10, scale: 0.97 }}
                                            className="glass-card absolute right-0 mt-3 w-[320px] p-4"
                                        >
                                            <div className="mb-3 flex items-center justify-between">
                                                <p className="text-xs font-bold uppercase tracking-[0.18em] text-ink-soft">{t('layout.notifications')}</p>
                                                <span className="text-xs font-semibold text-primary">{t('layout.markAllRead')}</span>
                                            </div>
                                            <div className="space-y-3">
                                                {notifications.map((notification) => (
                                                    <div key={notification.id} className="clay-panel-pressed rounded-[1.4rem] p-4">
                                                        <div className="flex items-start justify-between gap-3">
                                                            <div>
                                                                <p className="text-sm font-semibold text-ink">{notification.title}</p>
                                                                <p className="mt-1 text-xs leading-6 text-ink-muted">{notification.desc}</p>
                                                            </div>
                                                            <span className="text-[11px] font-semibold text-ink-soft">{notification.time}</span>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </MotionDiv>
                                    )}
                                </AnimatePresence>
                            </div>
                            <button
                                onClick={walletAddress ? undefined : handleConnectWallet}
                                className={walletAddress ? 'clay-button clay-button-primary text-white' : 'clay-button'}
                            >
                                <Wallet className="h-4 w-4" />
                                {walletAddress ? formatAddress(walletAddress) : t('layout.connectWallet')}
                            </button>
                        </div>
                    </div>

                    <div className="mx-auto flex w-full max-w-7xl flex-1 flex-col px-1 lg:px-0">
                        <MotionDiv
                            key={location.pathname}
                            initial={{ opacity: 0, y: 16 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.32, ease: [0.2, 0.9, 0.2, 1] }}
                            className="flex-1"
                        >
                            {children}
                        </MotionDiv>
                        <Footer />
                    </div>
                </main>
            </div>
        </div>
    );
}
