import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import {
    LayoutDashboard,
    Dna,
    Upload,
    FlaskConical,
    Wallet,
    LogOut,
    Menu,
    X,
    Building2,
    Bell,
    ChevronDown,
    Newspaper,
    Cpu,
    MessageSquare
} from 'lucide-react';
import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Footer from './Footer';

export default function Layout({ children }) {
    const { user, logout, walletAddress, connectWallet } = useAuth();
    const location = useLocation();
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
    const [notificationsOpen, setNotificationsOpen] = useState(false);
    const MotionDiv = motion.div;

    const [notifications, setNotifications] = useState([
        { id: 1, title: 'Funding Approved', desc: 'Your research DAO "GenCore" received 150 USDC', time: '1h ago', unread: true },
        { id: 2, title: 'New Peer Review', desc: 'Dr. Smith reviewed your latest submission', time: '3h ago', unread: true },
        { id: 3, title: 'Token Airdrop', desc: 'Claim your early researcher SCI tokens', time: '2d ago', unread: false },
    ]);

    const addNotification = useCallback((title, desc) => {
        const newNotif = {
            id: Date.now(),
            title,
            desc,
            time: 'Just now',
            unread: true
        };
        setNotifications(prev => [newNotif, ...prev]);
    }, []);

    const handleConnectWallet = async () => {
        const result = await connectWallet();
        if (result.success) {
            addNotification('Wallet Connected', `Successfully linked wallet ${formatAddress(result.address)}`);
        } else {
            alert(result.error || '지갑 연결에 실패했습니다.');
        }
    };

    const formatAddress = (address) => {
        if (!address) return '';
        return `${address.substring(0, 6)}...${address.substring(address.length - 4)}`;
    };

    const navigation = [
        { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
        { name: 'BioLinker', href: '/biolinker', icon: Dna },
        { name: 'Paper Upload', href: '/upload', icon: Upload },
        { name: 'My Lab', href: '/mylab', icon: FlaskConical },
        { name: 'Notices', href: '/notices', icon: Newspaper },
        { name: 'VC Portal', href: '/vc-portal', icon: Building2 },
        { name: 'AI Lab', href: '/ai-lab', icon: Cpu },
        { name: 'Peer Review', href: '/peer-review', icon: MessageSquare },
        { name: 'Wallet', href: '/wallet', icon: Wallet },
    ];

    const isActive = (path) => location.pathname === path;

    useEffect(() => {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setIsMobileMenuOpen(false);
    }, [location.pathname]);

    const handleKeyDown = useCallback((e) => {
        if (e.key === 'Escape' && isMobileMenuOpen) {
            setIsMobileMenuOpen(false);
        }
    }, [isMobileMenuOpen]);

    useEffect(() => {
        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, [handleKeyDown]);

    useEffect(() => {
        if (isMobileMenuOpen) {
            document.body.style.overflow = 'hidden';
        } else {
            document.body.style.overflow = '';
        }
        return () => {
            document.body.style.overflow = '';
        };
    }, [isMobileMenuOpen]);

    return (
        <div className="min-h-screen relative">
            {/* Ambient background */}
            <div className="ambient-bg" aria-hidden="true" />

            {/* Floating glow orbs */}
            <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden" aria-hidden="true">
                <div className="glow-orb glow-orb-primary w-[600px] h-[600px] -top-60 left-[10%] animate-blob" />
                <div className="glow-orb glow-orb-accent w-[500px] h-[500px] top-[40%] -right-40 animate-blob animation-delay-4000" />
                <div className="glow-orb glow-orb-highlight w-[300px] h-[300px] bottom-[10%] left-[30%] animate-blob animation-delay-6000" />
            </div>

            {/* Mobile Header */}
            <header className="lg:hidden flex items-center justify-between p-4 glass border-b border-white/[0.06] sticky top-0 z-40">
                <Link to="/dashboard" className="flex items-center gap-2.5">
                    <div className="p-1.5 rounded-lg" style={{ background: 'linear-gradient(135deg, rgba(0,212,170,0.15), rgba(99,102,241,0.15))' }}>
                        <Dna className="w-5 h-5 text-primary" aria-hidden="true" />
                    </div>
                    <span className="font-display text-lg font-bold text-white tracking-tight">DSCI</span>
                </Link>
                <button
                    onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                    className="p-2 text-white/70 hover:text-white hover:bg-white/[0.06] rounded-lg transition-colors"
                    aria-expanded={isMobileMenuOpen}
                    aria-controls="mobile-menu"
                    aria-label={isMobileMenuOpen ? 'Close menu' : 'Open menu'}
                >
                    {isMobileMenuOpen ? <X size={22} /> : <Menu size={22} />}
                </button>
            </header>

            <div className="flex min-h-screen relative z-10">
                {/* Sidebar */}
                <aside
                    id="mobile-menu"
                    role="navigation"
                    aria-label="Main navigation"
                    className={`
                        fixed lg:static inset-y-0 left-0 z-50 w-[260px] transform transition-transform duration-300 ease-[cubic-bezier(.16,1,.3,1)]
                        ${isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
                        bg-[#040811]/90 backdrop-blur-2xl border-r border-white/[0.04] p-5 flex flex-col justify-between
                    `}
                >
                    <div>
                        {/* Desktop Logo */}
                        <Link
                            to="/dashboard"
                            className="hidden lg:flex items-center gap-3 mb-10 px-3 py-2 group"
                        >
                            <div className="p-2 rounded-xl relative overflow-hidden" style={{ background: 'linear-gradient(135deg, rgba(0,212,170,0.12), rgba(99,102,241,0.12))' }}>
                                <Dna className="w-6 h-6 text-primary relative z-10 group-hover:scale-110 transition-transform" aria-hidden="true" />
                            </div>
                            <div>
                                <h1 className="font-display font-bold text-lg leading-none text-white tracking-tight">DSCI</h1>
                                <p className="text-[11px] text-white/30 mt-0.5 tracking-wider uppercase">DecentBio</p>
                            </div>
                        </Link>

                        <nav className="space-y-1" aria-label="Sidebar navigation">
                            {navigation.map((item) => {
                                const Icon = item.icon;
                                const active = isActive(item.href);
                                return (
                                    <Link
                                        key={item.name}
                                        to={item.href}
                                        aria-current={active ? 'page' : undefined}
                                        className={`
                                            flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 relative overflow-hidden group
                                            focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 focus-visible:ring-offset-2 focus-visible:ring-offset-[#040811]
                                            ${active
                                                ? 'text-white'
                                                : 'text-white/40 hover:text-white/80 hover:bg-white/[0.03]'}
                                        `}
                                    >
                                        {active && (
                                            <MotionDiv
                                                layoutId="activeTab"
                                                className="absolute inset-0 rounded-xl"
                                                style={{
                                                    background: 'linear-gradient(135deg, rgba(0,212,170,0.12), rgba(99,102,241,0.08))',
                                                    border: '1px solid rgba(0,212,170,0.15)',
                                                }}
                                                initial={false}
                                                transition={{ type: "spring", stiffness: 400, damping: 30 }}
                                                aria-hidden="true"
                                            />
                                        )}
                                        {active && (
                                            <MotionDiv
                                                layoutId="activeIndicator"
                                                className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-full bg-primary"
                                                initial={false}
                                                transition={{ type: "spring", stiffness: 400, damping: 30 }}
                                                aria-hidden="true"
                                            />
                                        )}
                                        <div className="relative z-10 flex items-center gap-3">
                                            <Icon className={`w-[18px] h-[18px] ${active ? 'text-primary' : 'group-hover:text-white/60'}`} aria-hidden="true" />
                                            <span className="text-sm font-medium">{item.name}</span>
                                        </div>
                                    </Link>
                                );
                            })}
                        </nav>
                    </div>

                    {/* User section */}
                    <div className="pt-5 border-t border-white/[0.04] mt-auto">
                        <div className="flex items-center gap-3 px-3 mb-3">
                            {user?.photoURL ? (
                                <img
                                    src={user.photoURL}
                                    alt={`${user?.displayName || 'User'}'s profile`}
                                    className="w-9 h-9 rounded-xl border border-white/10 object-cover"
                                />
                            ) : (
                                <div
                                    className="w-9 h-9 rounded-xl flex items-center justify-center text-sm font-bold text-white"
                                    style={{ background: 'linear-gradient(135deg, rgba(0,212,170,0.3), rgba(99,102,241,0.3))' }}
                                    aria-hidden="true"
                                >
                                    {user?.email?.[0].toUpperCase()}
                                </div>
                            )}
                            <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-white/80 truncate">
                                    {user?.displayName || 'Researcher'}
                                </p>
                                <p className="text-[11px] text-white/30 truncate">{user?.email}</p>
                            </div>
                        </div>

                        <button
                            onClick={logout}
                            className="w-full flex items-center gap-3 px-3 py-2.5 text-white/30 hover:text-red-400 hover:bg-red-500/[0.06] rounded-xl transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500/50"
                            aria-label="Sign out of your account"
                        >
                            <LogOut className="w-[18px] h-[18px]" aria-hidden="true" />
                            <span className="text-sm font-medium">Sign Out</span>
                        </button>
                    </div>
                </aside>

                {/* Overlay for mobile */}
                <AnimatePresence>
                    {isMobileMenuOpen && (
                        <MotionDiv
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            transition={{ duration: 0.2 }}
                            className="fixed inset-0 bg-black/70 backdrop-blur-sm z-40 lg:hidden"
                            onClick={() => setIsMobileMenuOpen(false)}
                            aria-hidden="true"
                        />
                    )}
                </AnimatePresence>

                {/* Main Content Area */}
                <main
                    id="main-content"
                    className="flex-1 overflow-y-auto h-screen scrollbar-hide flex flex-col"
                    role="main"
                >
                    {/* Topbar (Desktop) */}
                    <div className="hidden lg:flex items-center justify-end gap-x-5 px-6 py-3 border-b border-white/[0.04] bg-[#040811]/60 sticky top-0 z-30 backdrop-blur-xl">
                        {/* Notifications */}
                        <div className="relative">
                            <button
                              onClick={() => setNotificationsOpen(!notificationsOpen)}
                              className="relative p-2 text-white/30 hover:text-white/60 transition-colors focus:outline-none rounded-lg hover:bg-white/[0.04]"
                            >
                                <Bell className="w-5 h-5" />
                                {notifications.filter(n => n.unread).length > 0 && (
                                    <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-primary rounded-full z-10 animate-pulse"></span>
                                )}
                            </button>

                            <AnimatePresence>
                                {notificationsOpen && (
                                    <MotionDiv
                                      initial={{ opacity: 0, scale: 0.95, y: 8 }}
                                      animate={{ opacity: 1, scale: 1, y: 0 }}
                                      exit={{ opacity: 0, scale: 0.95, y: 8 }}
                                      className="absolute right-0 mt-2 w-80 bg-surface-raised/95 backdrop-blur-xl border border-white/[0.08] rounded-2xl shadow-2xl py-1 z-50 overflow-hidden"
                                      style={{ boxShadow: '0 24px 48px rgba(0,0,0,0.6)' }}
                                    >
                                        <div className="px-4 py-3 border-b border-white/[0.06] flex justify-between items-center">
                                            <h3 className="text-sm font-display font-semibold text-white">Notifications</h3>
                                            <span className="text-xs text-primary cursor-pointer hover:underline underline-offset-2">Mark all read</span>
                                        </div>
                                        <div className="max-h-64 overflow-y-auto">
                                            {notifications.map(n => (
                                                <div key={n.id} className={`p-4 border-b border-white/[0.03] hover:bg-white/[0.03] cursor-pointer transition-colors ${n.unread ? 'bg-primary/[0.03]' : ''}`}>
                                                    <div className="flex justify-between items-start mb-1">
                                                        <h4 className="text-sm font-medium text-white/90">{n.title}</h4>
                                                        <span className="text-[11px] text-white/25">{n.time}</span>
                                                    </div>
                                                    <p className="text-xs text-white/40 line-clamp-2">{n.desc}</p>
                                                </div>
                                            ))}
                                        </div>
                                        <div className="p-2.5 text-center text-xs text-white/30 hover:text-white/60 cursor-pointer transition-colors border-t border-white/[0.04]">
                                            View all notifications
                                        </div>
                                    </MotionDiv>
                                )}
                            </AnimatePresence>
                        </div>

                        {/* Wallet Connection */}
                        <button
                            onClick={walletAddress ? () => {} : handleConnectWallet}
                            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-300 ${
                                walletAddress
                                  ? 'bg-primary/10 text-primary border border-primary/20 hover:border-primary/30'
                                  : 'bg-white/[0.04] text-white/50 hover:text-white/70 hover:bg-white/[0.06] border border-white/[0.06]'
                            }`}
                        >
                            <Wallet className="w-4 h-4" />
                            {walletAddress ? formatAddress(walletAddress) : 'Connect Wallet'}
                            {walletAddress && <ChevronDown className="w-3 h-3 ml-1" />}
                        </button>
                    </div>

                    <div className="flex-1 p-4 lg:p-8 max-w-7xl w-full mx-auto">
                        <AnimatePresence mode="wait">
                            <MotionDiv
                                key={location.pathname}
                                initial={{ opacity: 0, y: 16 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -16 }}
                                transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
                            >
                                {children}
                            </MotionDiv>
                        </AnimatePresence>
                        <Footer />
                    </div>
                </main>
            </div>
        </div>
    );
}
