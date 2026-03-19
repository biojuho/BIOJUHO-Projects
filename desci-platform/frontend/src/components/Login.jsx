import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowRight, Sparkles, Globe2, ShieldCheck, TrendingUp } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';
import { useLocale } from '../contexts/LocaleContext';
import Button from './ui/Button';
import Input from './ui/Input';
import LocaleToggle from './ui/LocaleToggle';

const MotionDiv = motion.div;

const valueIcons = [Globe2, TrendingUp, ShieldCheck];

export default function Login() {
    const [isSignUp, setIsSignUp] = useState(false);
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [loading, setLoading] = useState(false);

    const { loginWithGoogle, loginWithEmail, signUpWithEmail } = useAuth();
    const { showToast } = useToast();
    const { t } = useLocale();
    const navigate = useNavigate();

    const values = [t('login.valueFunding'), t('login.valueMatching'), t('login.valueGovernance')];

    const handleGoogleLogin = async () => {
        setLoading(true);
        const result = await loginWithGoogle();
        if (result.success) {
            showToast({ key: 'login.welcome' }, 'success');
            navigate('/dashboard');
        } else {
            showToast(result.error || t('login.loginFailed'), 'error');
        }
        setLoading(false);
    };

    const handleEmailSubmit = async (event) => {
        event.preventDefault();

        if (password.length < 6) {
            showToast({ key: 'login.passwordTooShort' }, 'warning');
            return;
        }

        setLoading(true);
        const result = isSignUp
            ? await signUpWithEmail(email, password)
            : await loginWithEmail(email, password);

        if (result.success) {
            showToast({ key: 'login.authSuccess' }, 'success');
            navigate('/dashboard');
        } else {
            showToast(result.error || t('login.authFailed'), 'error');
        }

        setLoading(false);
    };

    return (
        <div className="relative min-h-screen overflow-hidden px-4 py-4 lg:px-5 lg:py-5">
            <div className="ambient-bg" aria-hidden="true" />
            <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
                <div className="hero-orb hero-orb-mint left-[8%] top-[8%] h-56 w-56 animate-float" />
                <div className="hero-orb hero-orb-sky right-[10%] top-[16%] h-56 w-56 animate-float" />
                <div className="hero-orb hero-orb-peach bottom-[10%] left-[40%] h-44 w-44 animate-float" />
            </div>

            <div className="relative z-10 mx-auto flex max-w-7xl flex-col gap-5 lg:min-h-[calc(100vh-2.5rem)] lg:flex-row lg:items-center lg:gap-8">
                <MotionDiv
                    initial={{ opacity: 0, x: -24 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="glass-card hidden flex-1 p-8 xl:p-10 lg:flex lg:flex-col"
                >
                    <div className="flex-1">
                        <div className="mb-7 flex items-start justify-between gap-4 xl:mb-8">
                            <div className="flex items-center gap-3">
                                <div className="flex h-14 w-14 items-center justify-center rounded-[1.6rem] bg-gradient-to-br from-primary to-accent text-white shadow-clay-soft">
                                    <Sparkles className="h-6 w-6" />
                                </div>
                                <div>
                                    <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-ink-soft">{t('login.eyebrow')}</p>
                                    <h1 className="font-display text-4xl font-semibold text-ink">{t('login.title')}</h1>
                                </div>
                            </div>
                            <LocaleToggle />
                        </div>

                        <h2 className="text-balance max-w-[11ch] font-display text-[clamp(3rem,5vw,4.8rem)] font-semibold leading-[0.96] text-ink">
                            {t('login.headline')}
                        </h2>
                        <p className="mt-4 max-w-2xl text-base leading-7 text-ink-muted xl:text-lg xl:leading-8">
                            {isSignUp ? t('login.subtitleSignup') : t('login.subtitleSignin')}
                        </p>

                        <div className="mt-7 grid gap-4 md:grid-cols-3 xl:gap-5">
                            {values.map((value, index) => {
                                const Icon = valueIcons[index];
                                return (
                                    <div key={value} className="clay-panel-pressed min-h-[132px] rounded-[1.8rem] p-5">
                                        <Icon className="mb-4 h-5 w-5 text-primary" />
                                        <p className="text-sm font-semibold leading-6 text-ink">{value}</p>
                                    </div>
                                );
                            })}
                        </div>

                        <div className="mt-7 grid gap-4 xl:grid-cols-2">
                            <div className="clay-panel h-full p-6">
                                <p className="clay-chip mb-4">{t('layout.workspace')}</p>
                                <p className="text-sm leading-7 text-ink-muted">{t('login.roleResearchers')}</p>
                            </div>
                            <div className="clay-panel h-full p-6">
                                <p className="clay-chip mb-4">{t('layout.market')}</p>
                                <p className="text-sm leading-7 text-ink-muted">{t('login.roleFunders')}</p>
                            </div>
                        </div>
                    </div>

                    <p className="mt-8 pt-5 text-xs font-bold uppercase tracking-[0.24em] text-ink-soft">{t('login.protocol')}</p>
                </MotionDiv>

                <MotionDiv
                    initial={{ opacity: 0, x: 24 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.08 }}
                    className="glass-card relative w-full max-w-xl p-6 sm:p-8 xl:max-w-[34rem] xl:p-10"
                >
                    <div className="mb-7 flex items-start justify-between gap-4 lg:hidden">
                        <div>
                            <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-ink-soft">{t('login.eyebrow')}</p>
                            <h1 className="font-display text-3xl font-semibold text-ink">{t('login.title')}</h1>
                        </div>
                        <LocaleToggle />
                    </div>

                    <div className="space-y-7">
                        <div>
                            <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-ink-soft">
                                {isSignUp ? t('login.signUp') : t('login.signIn')}
                            </p>
                            <h2 className="text-balance mt-2 max-w-[11ch] font-display text-[clamp(2.35rem,4.5vw,3.8rem)] font-semibold leading-[1.02] text-ink">
                                <span className="text-gradient">{t('login.panelTitle')}</span>
                            </h2>
                            <p className="mt-3 max-w-xl text-sm leading-7 text-ink-muted">
                                {isSignUp ? t('login.subtitleSignup') : t('login.subtitleSignin')}
                            </p>
                        </div>

                        <button
                            onClick={handleGoogleLogin}
                            disabled={loading}
                            aria-label={t('login.continueWithGoogle')}
                            className="clay-button clay-button-primary w-full justify-center text-white"
                        >
                            <svg className="h-5 w-5" viewBox="0 0 24 24" aria-hidden="true">
                                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                            </svg>
                            <span>{t('login.continueWithGoogle')}</span>
                            <ArrowRight className="h-4 w-4" />
                        </button>

                        <div className="flex items-center gap-4">
                            <div className="soft-divider flex-1" />
                            <span className="text-[11px] font-bold uppercase tracking-[0.18em] text-ink-soft">{t('login.orWithEmail')}</span>
                            <div className="soft-divider flex-1" />
                        </div>

                        <form onSubmit={handleEmailSubmit} className="space-y-4" aria-label={isSignUp ? t('login.signUpForm') : t('login.signInForm')}>
                            <div>
                                <label className="mb-2 block text-sm font-semibold text-ink">{t('login.emailLabel')}</label>
                                <Input
                                    type="email"
                                    value={email}
                                    onChange={(event) => setEmail(event.target.value)}
                                    required
                                    autoComplete="email"
                                    placeholder={t('login.emailPlaceholder')}
                                />
                            </div>
                            <div>
                                <label className="mb-2 block text-sm font-semibold text-ink">{t('login.passwordLabel')}</label>
                                <Input
                                    type="password"
                                    value={password}
                                    onChange={(event) => setPassword(event.target.value)}
                                    required
                                    minLength={6}
                                    autoComplete={isSignUp ? 'new-password' : 'current-password'}
                                    placeholder={t('login.passwordPlaceholder')}
                                />
                                <p className="mt-2 text-xs text-ink-soft">{t('login.passwordHelper')}</p>
                            </div>

                            <Button type="submit" loading={loading} className="w-full justify-center text-white">
                                {isSignUp ? t('login.createAccount') : t('login.signIn')}
                            </Button>
                        </form>
                    </div>

                    <p className="mt-6 text-center text-sm text-ink-muted">
                        {isSignUp ? t('login.alreadyHaveAccount') : t('login.newToDecentBio')}{' '}
                        <button
                            type="button"
                            onClick={() => setIsSignUp((value) => !value)}
                            className="font-semibold text-primary hover:underline"
                        >
                            {isSignUp ? t('login.signIn') : t('login.signUp')}
                        </button>
                    </p>
                </MotionDiv>
            </div>
        </div>
    );
}
