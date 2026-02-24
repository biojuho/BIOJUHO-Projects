/**
 * Login Component
 * Google + Email/Password authentication
 * Design: Bioluminescent Neural Network
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';
import Button from './ui/Button';
import Input from './ui/Input';
// eslint-disable-next-line no-unused-vars
import { motion } from 'framer-motion';
import { Dna, ArrowRight } from 'lucide-react';

export default function Login() {
    const [isSignUp, setIsSignUp] = useState(false);
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [loading, setLoading] = useState(false);

    const { loginWithGoogle, loginWithEmail, signUpWithEmail } = useAuth();
    const { showToast } = useToast();
    const navigate = useNavigate();

    const handleGoogleLogin = async () => {
        setLoading(true);
        const result = await loginWithGoogle();
        if (result.success) {
            showToast('환영합니다! 👋', 'success');
            navigate('/dashboard');
        } else {
            showToast(result.error || '로그인에 실패했습니다.', 'error');
        }
        setLoading(false);
    };

    const handleEmailSubmit = async (e) => {
        e.preventDefault();

        if (password.length < 6) {
            showToast('비밀번호는 6자 이상이어야 합니다.', 'warning');
            return;
        }

        setLoading(true);

        const result = isSignUp
            ? await signUpWithEmail(email, password)
            : await loginWithEmail(email, password);

        if (result.success) {
            showToast('성공적으로 로그인되었습니다! 🎉', 'success');
            navigate('/dashboard');
        } else {
            showToast(result.error || '인증에 실패했습니다.', 'error');
        }
        setLoading(false);
    };

    return (
        <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden bg-[#040811]">
            {/* Ambient background */}
            <div className="ambient-bg" aria-hidden="true" />

            {/* Bioluminescent glow orbs */}
            <div className="absolute inset-0 z-0 overflow-hidden" aria-hidden="true">
                <div className="glow-orb glow-orb-primary w-[500px] h-[500px] -top-40 -left-20 animate-blob" />
                <div className="glow-orb glow-orb-accent w-[600px] h-[600px] -bottom-40 -right-20 animate-blob animation-delay-2000" />
                <div className="glow-orb glow-orb-highlight w-[400px] h-[400px] top-1/3 right-1/4 animate-blob animation-delay-4000" />
            </div>

            {/* Decorative neural lines */}
            <div className="absolute inset-0 z-0" aria-hidden="true">
                <div className="absolute top-1/4 left-0 right-0 neural-line opacity-40" />
                <div className="absolute top-3/4 left-0 right-0 neural-line opacity-20" />
            </div>

            {/* Login Card */}
            <motion.div
                initial={{ opacity: 0, y: 30, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                className="w-full max-w-md relative z-10"
            >
                <div className="relative rounded-3xl overflow-hidden">
                    {/* Gradient border effect */}
                    <div className="absolute inset-0 rounded-3xl p-[1px] bg-gradient-to-br from-primary/30 via-accent/20 to-primary/10 pointer-events-none" />

                    <div className="relative bg-surface/80 backdrop-blur-2xl rounded-3xl p-8 sm:p-10 border border-white/[0.06]"
                         style={{ boxShadow: '0 32px 64px rgba(0, 0, 0, 0.6), 0 0 80px rgba(0, 212, 170, 0.05)' }}>

                        {/* Header */}
                        <header className="text-center mb-10">
                            <motion.div
                                initial={{ scale: 0.5, opacity: 0, rotate: -180 }}
                                animate={{ scale: 1, opacity: 1, rotate: 0 }}
                                transition={{ type: "spring", stiffness: 200, damping: 15, delay: 0.2 }}
                                className="inline-flex p-4 rounded-2xl mb-5 relative"
                                style={{ background: 'linear-gradient(135deg, rgba(0, 212, 170, 0.1), rgba(99, 102, 241, 0.1))' }}
                            >
                                <div className="absolute inset-0 rounded-2xl animate-glow-pulse"
                                     style={{ background: 'radial-gradient(circle, rgba(0, 212, 170, 0.2), transparent 70%)' }} />
                                <Dna className="w-10 h-10 text-primary relative z-10" aria-hidden="true" />
                            </motion.div>

                            <motion.div
                                initial={{ y: 20, opacity: 0 }}
                                animate={{ y: 0, opacity: 1 }}
                                transition={{ delay: 0.3, duration: 0.5 }}
                            >
                                <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight">
                                    <span className="text-white">Decent</span>
                                    <span className="text-gradient">Bio</span>
                                </h1>
                                <p className="text-secondary mt-3 text-sm leading-relaxed">
                                    {isSignUp
                                        ? 'Join the decentralized science network'
                                        : 'Welcome back to the future of science'}
                                </p>
                            </motion.div>
                        </header>

                        {/* Google Login */}
                        <motion.button
                            initial={{ y: 20, opacity: 0 }}
                            animate={{ y: 0, opacity: 1 }}
                            transition={{ delay: 0.4 }}
                            onClick={handleGoogleLogin}
                            disabled={loading}
                            aria-label="Continue with Google account"
                            className="w-full flex items-center justify-center gap-3 bg-white/[0.07] text-white font-medium py-3.5 px-4 rounded-xl
                                       hover:bg-white/[0.12] transition-all duration-300 border border-white/[0.08] hover:border-white/[0.15]
                                       active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed mb-8
                                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 focus-visible:ring-offset-2 focus-visible:ring-offset-surface
                                       group"
                            style={{ boxShadow: 'inset 0 1px 0 0 rgba(255,255,255,0.04)' }}
                        >
                            <svg className="w-5 h-5" viewBox="0 0 24 24" aria-hidden="true">
                                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                            </svg>
                            <span>Continue with Google</span>
                            <ArrowRight className="w-4 h-4 opacity-0 -translate-x-2 group-hover:opacity-60 group-hover:translate-x-0 transition-all duration-300" />
                        </motion.button>

                        {/* Divider */}
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ delay: 0.5 }}
                            className="flex items-center my-8"
                            role="separator"
                        >
                            <div className="flex-1 neural-line"></div>
                            <span className="px-4 text-secondary text-xs uppercase tracking-[0.15em] font-medium">Or with email</span>
                            <div className="flex-1 neural-line"></div>
                        </motion.div>

                        {/* Email Form */}
                        <motion.form
                            initial={{ y: 20, opacity: 0 }}
                            animate={{ y: 0, opacity: 1 }}
                            transition={{ delay: 0.6 }}
                            onSubmit={handleEmailSubmit}
                            className="space-y-5"
                            aria-label={isSignUp ? 'Sign up form' : 'Sign in form'}
                        >
                            <Input
                                type="email"
                                label="Email"
                                placeholder="you@example.com"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                required
                                autoComplete="email"
                            />
                            <Input
                                type="password"
                                label="Password"
                                placeholder="Enter your password"
                                helperText={isSignUp ? 'Minimum 6 characters' : undefined}
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                                minLength={6}
                                autoComplete={isSignUp ? 'new-password' : 'current-password'}
                            />

                            <Button
                                type="submit"
                                loading={loading}
                                fullWidth
                                size="lg"
                            >
                                {isSignUp ? 'Create Account' : 'Sign In'}
                            </Button>
                        </motion.form>

                        {/* Toggle Sign Up / Login */}
                        <motion.p
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ delay: 0.7 }}
                            className="text-center text-secondary mt-8 text-sm"
                        >
                            {isSignUp ? 'Already have an account?' : 'New to DecentBio?'}{' '}
                            <button
                                type="button"
                                onClick={() => setIsSignUp(!isSignUp)}
                                className="text-primary hover:text-primary-300 font-medium hover:underline underline-offset-4 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 rounded"
                            >
                                {isSignUp ? 'Sign In' : 'Sign Up'}
                            </button>
                        </motion.p>
                    </div>
                </div>

                {/* Tagline below card */}
                <motion.p
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 1, duration: 1 }}
                    className="text-center text-white/20 text-xs mt-6 tracking-widest uppercase font-display"
                >
                    Decentralized Science Protocol
                </motion.p>
            </motion.div>
        </div>
    );
}
