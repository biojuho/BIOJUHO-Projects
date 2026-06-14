import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { AlertCircle, ArrowLeft, Building2, Check, CheckCircle2, CreditCard, Lock, Minus, Sparkles, Zap } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useLocale } from '../contexts/LocaleContext';
import { useDocumentMeta } from '../hooks/useDocumentMeta';
import api, { formatApiError } from '../services/api';
import GlassCard from './ui/GlassCard';
import { Badge } from './ui/Badge';
import LocaleToggle from './ui/LocaleToggle';

const TIERS = [
    {
        id: 'free',
        icon: Sparkles,
        name: 'Starter',
        price: { monthly: 0, yearly: 0 },
        descKo: '연구 탐색을 시작하는 팀을 위한 무료 플랜',
        descEn: 'For researchers getting started with DeSci',
        features: [
            { textKo: '정부 과제 검색 월 10건', textEn: '10 grant searches / month', included: true },
            { textKo: 'AI 적합도 분석 월 3건', textEn: '3 AI analyses / month', included: true },
            { textKo: 'IPFS 논문 업로드 3건', textEn: '3 IPFS paper uploads', included: true },
            { textKo: 'VC 매칭 결과 보기', textEn: 'VC matching results', included: true },
            { textKo: '기본 DSCI 보상', textEn: 'Basic DSCI rewards', included: true },
            { textKo: 'AI 제안서 자동 생성', textEn: 'AI proposal generation', included: false },
            { textKo: '문헌 리뷰 자동화', textEn: 'Literature review automation', included: false },
        ],
        ctaKo: '현재 플랜',
        ctaEn: 'Current plan',
        popular: false,
    },
    {
        id: 'pro',
        icon: Zap,
        name: 'Pro',
        price: { monthly: 29, yearly: 290 },
        descKo: '본격적인 연구 개발과 사업화를 위한 플랜',
        descEn: 'For serious researchers and bio-startups',
        features: [
            { textKo: '정부 과제 검색 무제한', textEn: 'Unlimited grant searches', included: true },
            { textKo: 'AI 적합도 분석 월 30건', textEn: '30 AI analyses / month', included: true },
            { textKo: 'AI 제안서 초안 월 5건', textEn: '5 AI proposal drafts / month', included: true },
            { textKo: 'VC 매칭과 연락처 정보', textEn: 'VC matching + contact info', included: true },
            { textKo: 'IPFS 논문 업로드 30건', textEn: '30 IPFS paper uploads', included: true },
            { textKo: '문헌 리뷰 월 10건', textEn: '10 literature reviews / month', included: true },
            { textKo: 'DSCI 토큰 보상 2배', textEn: '2x DSCI token rewards', included: true },
        ],
        ctaKo: 'Pro로 업그레이드',
        ctaEn: 'Upgrade to Pro',
        popular: true,
    },
    {
        id: 'enterprise',
        icon: Building2,
        name: 'Enterprise',
        price: { monthly: 199, yearly: 1990 },
        descKo: '기관과 바이오 기업을 위한 운영형 플랜',
        descEn: 'For institutions and biotech companies',
        features: [
            { textKo: '모든 기능 무제한', textEn: 'All features unlimited', included: true },
            { textKo: '맞춤형 AI 제안서', textEn: 'Custom AI proposals', included: true },
            { textKo: '전담 계정 매니저', textEn: 'Dedicated account manager', included: true },
            { textKo: '우선 기술 지원', textEn: 'Priority technical support', included: true },
            { textKo: '맞춤 DSCI 보상 설계', textEn: 'Custom DSCI reward design', included: true },
            { textKo: 'API 접근 120 req/min', textEn: 'API access (120 req/min)', included: true },
            { textKo: '온프레미스 배포 지원', textEn: 'On-premise deployment', included: true },
        ],
        ctaKo: '영업팀 문의',
        ctaEn: 'Contact sales',
        popular: false,
    },
];

const ENTERPRISE_CONTACT_HREF = 'mailto:hello@decentbio.xyz?subject=Enterprise Plan Inquiry';
const STRIPE_CHECKOUT_HOSTS = new Set(['checkout.stripe.com']);
const STRIPE_PORTAL_HOSTS = new Set(['billing.stripe.com']);

function buildStripeRedirectUrl(candidate, allowedHosts) {
    const value = String(candidate || '').trim();
    if (!value) return '';

    try {
        const url = new URL(value);
        if (url.protocol === 'https:' && allowedHosts.has(url.hostname)) {
            return url.href;
        }

        if (import.meta.env.DEV && typeof window !== 'undefined') {
            const current = new URL(window.location.href);
            if (url.origin === current.origin && ['http:', 'https:'].includes(url.protocol)) {
                return url.href;
            }
        }
    } catch {
        return '';
    }

    return '';
}

export default function PricingPage() {
    const { user } = useAuth();
    const { locale } = useLocale();
    const navigate = useNavigate();
    const location = useLocation();
    const isKo = locale === 'ko-KR';
    useDocumentMeta({
        title: isKo ? '요금제 — DecentBio' : 'Pricing — DecentBio',
        description: isKo
            ? 'Starter 무료, Pro $29/월, Enterprise $199/월. 연구 규모에 맞는 플랜을 선택하세요.'
            : 'Starter free, Pro $29/mo, Enterprise $199/mo. Choose the plan that fits your research.',
        canonicalPath: '/pricing',
    });
    const isSuccessRoute = location.pathname === '/subscription/success';
    const searchParams = new URLSearchParams(location.search);
    const sessionId = searchParams.get('session_id') || '';
    const checkoutStatus = searchParams.get('checkout') || '';
    const cancelledPlanParam = searchParams.get('plan') || 'pro';
    const cancelledPlan = TIERS.some((tier) => tier.id === cancelledPlanParam && tier.id !== 'free')
        ? cancelledPlanParam
        : 'pro';
    const cancelledBillingParam = searchParams.get('billing') || 'monthly';
    const cancelledBilling = ['monthly', 'yearly'].includes(cancelledBillingParam) ? cancelledBillingParam : 'monthly';
    const isCancelledCheckout = checkoutStatus === 'cancelled' || checkoutStatus === 'canceled';
    const cancelledTierName = TIERS.find((tier) => tier.id === cancelledPlan)?.name || cancelledPlan;
    const [billing, setBilling] = useState(cancelledBilling);
    const [loadingTier, setLoadingTier] = useState(null);
    const [billingPortalLoading, setBillingPortalLoading] = useState(false);
    const [checkoutError, setCheckoutError] = useState('');
    const [accountTier, setAccountTier] = useState('free');
    const currentTier = user ? accountTier : 'free';

    useEffect(() => {
        if (!user) return;

        api.get('/subscription/tier')
            .then((response) => setAccountTier(response.data?.tier || 'free'))
            .catch(() => {});
    }, [user]);

    const handleCheckout = async (tierId) => {
        setCheckoutError('');
        if (tierId === 'free' || tierId === currentTier) return;
        if (!user) {
            navigate(`/login?next=/pricing&plan=${tierId}`);
            return;
        }

        setLoadingTier(tierId);
        try {
            const { data } = await api.post(
                '/subscription/checkout',
                { tier: tierId, billing },
                { suppressErrorLog: true },
            );
            const checkoutUrl = buildStripeRedirectUrl(data.checkout_url, STRIPE_CHECKOUT_HOSTS);
            if (checkoutUrl) {
                window.location.assign(checkoutUrl);
            } else {
                setCheckoutError(isKo
                    ? 'Stripe checkout redirect URL is invalid. Try again or contact support.'
                    : 'Stripe checkout redirect URL is invalid. Try again or contact support.');
            }
        } catch (error) {
            setCheckoutError(formatApiError(
                error,
                isKo ? '결제 세션을 만들 수 없습니다. 잠시 후 다시 시도하거나 관리자에게 문의하세요.' : 'Could not create a checkout session. Try again or contact support.',
            ));
        } finally {
            setLoadingTier(null);
        }
    };

    const handleManageBilling = async () => {
        setCheckoutError('');
        if (!user) {
            navigate('/login?next=/pricing');
            return;
        }

        setBillingPortalLoading(true);
        try {
            const { data } = await api.post('/subscription/portal', {}, { suppressErrorLog: true });
            const portalUrl = buildStripeRedirectUrl(data.portal_url, STRIPE_PORTAL_HOSTS);
            if (portalUrl) {
                window.location.assign(portalUrl);
            } else {
                setCheckoutError(isKo
                    ? 'Stripe billing portal redirect URL is invalid. Contact support if the issue continues.'
                    : 'Stripe billing portal redirect URL is invalid. Contact support if the issue continues.');
            }
        } catch (error) {
            setCheckoutError(formatApiError(
                error,
                isKo ? 'Stripe billing portal could not be opened. Contact support if the issue continues.' : 'Stripe billing portal could not be opened. Contact support if the issue continues.',
            ));
        } finally {
            setBillingPortalLoading(false);
        }
    };

    if (isSuccessRoute) {
        return (
            <div className="relative min-h-screen" style={{ background: 'var(--bg-primary, #f0ece6)' }}>
                <div className="ambient-bg" aria-hidden="true" />

                <nav className="relative z-20 flex items-center justify-between px-6 py-5 lg:px-12">
                    <Link to="/" className="flex items-center gap-2 text-sm font-semibold text-ink-muted hover:text-ink">
                        <ArrowLeft className="h-4 w-4" />
                        {isKo ? '홈으로' : 'Back to home'}
                    </Link>
                    <div className="flex items-center gap-3">
                        <LocaleToggle />
                        <Link to="/dashboard" className="clay-button clay-button-primary text-sm font-semibold text-white">
                            <Sparkles className="h-4 w-4" />
                            {isKo ? '대시보드' : 'Dashboard'}
                        </Link>
                    </div>
                </nav>

                <main className="relative z-10 mx-auto flex min-h-[calc(100vh-96px)] max-w-4xl items-center px-6 py-16 lg:px-12">
                    <motion.div
                        initial={{ opacity: 0, y: 18 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.45 }}
                        className="w-full"
                        data-testid="pricing-success-panel"
                    >
                        <GlassCard className="p-8 text-center md:p-12">
                            <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-success/15 text-success shadow-clay-soft">
                                <CheckCircle2 className="h-8 w-8" />
                            </div>
                            <p className="clay-chip mb-4 inline-block">
                                {isKo ? '결제 완료' : 'Checkout complete'}
                            </p>
                            <h1 className="font-display text-4xl font-semibold text-ink md:text-5xl">
                                {isKo ? '구독이 활성화되는 중입니다' : 'Your subscription is being activated'}
                            </h1>
                            <p className="mx-auto mt-5 max-w-2xl text-base leading-7 text-ink-muted">
                                {isKo
                                    ? 'Stripe 결제가 완료되었습니다. 대시보드에서 출시 준비도와 사용 한도를 확인하고 바로 연구 워크플로를 이어가세요.'
                                    : 'Stripe checkout is complete. Review launch readiness and usage limits from the dashboard, then continue your research workflow.'}
                            </p>
                            {sessionId && (
                                <p className="mx-auto mt-5 max-w-xl rounded-[1rem] bg-white/60 px-4 py-3 font-mono text-xs text-ink-muted" data-testid="pricing-success-session">
                                    {isKo ? '세션' : 'Session'}: {sessionId}
                                </p>
                            )}
                            <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
                                <Link to="/dashboard" className="clay-button clay-button-primary px-8 py-4 text-base font-semibold text-white" data-testid="pricing-success-dashboard">
                                    <Sparkles className="h-5 w-5" />
                                    {isKo ? '대시보드에서 확인' : 'Open dashboard'}
                                </Link>
                                <Link to="/upload" className="clay-button px-8 py-4 text-base font-semibold text-ink" data-testid="pricing-success-upload">
                                    {isKo ? '논문 업로드 계속' : 'Continue to upload'}
                                </Link>
                            </div>
                        </GlassCard>
                    </motion.div>
                </main>
            </div>
        );
    }

    return (
        <div className="relative min-h-screen" style={{ background: 'var(--bg-primary, #f0ece6)' }}>
            <div className="ambient-bg" aria-hidden="true" />

            <nav className="relative z-20 flex items-center justify-between px-6 py-5 lg:px-12">
                <Link to="/" className="flex items-center gap-2 text-sm font-semibold text-ink-muted hover:text-ink">
                    <ArrowLeft className="h-4 w-4" />
                    {isKo ? '홈으로' : 'Back to home'}
                </Link>
                <div className="flex items-center gap-3">
                    <LocaleToggle />
                    {user ? (
                        <Link to="/dashboard" className="clay-button clay-button-primary text-sm font-semibold text-white">
                            <Sparkles className="h-4 w-4" />
                            {isKo ? '대시보드' : 'Dashboard'}
                        </Link>
                    ) : (
                        <Link to="/login" className="clay-button clay-button-primary text-sm font-semibold text-white">
                            {isKo ? '로그인' : 'Sign in'}
                        </Link>
                    )}
                </div>
            </nav>

            <div className="relative z-10 mx-auto max-w-7xl px-6 py-12 lg:px-12">
                <motion.div
                    initial={{ opacity: 0, y: -20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mb-12 text-center"
                >
                    <p className="clay-chip mb-4 inline-block">
                        {isKo ? '플랜 선택' : 'Choose your plan'}
                    </p>
                    <h1 className="font-display text-[clamp(2rem,5vw,3.5rem)] font-semibold text-ink">
                        {isKo ? '연구를 가속화할 플랜을 선택하세요' : 'Pick the plan that accelerates your research'}
                    </h1>
                    <p className="mx-auto mt-4 max-w-xl text-base leading-7 text-ink-muted">
                        {isKo
                            ? 'AI 기반 공고 탐색, 제안서 작성, 투자자 매칭을 팀 규모에 맞게 확장하세요.'
                            : 'Scale AI-assisted funding discovery, proposal drafting, and investor matching for your team.'}
                    </p>

                    <div
                        data-testid="pricing-trust-marker"
                        className="mt-5 inline-flex items-center gap-2 rounded-[1rem] bg-white/60 px-4 py-2 text-sm font-semibold text-ink-muted shadow-clay-soft"
                    >
                        <Lock className="h-4 w-4 text-primary" />
                        {isKo ? 'Stripe 蹂댁븞 寃곗젣' : 'Secured by Stripe'}
                    </div>

                    <div className="mt-8 inline-flex items-center gap-1 rounded-[1.2rem] bg-white/50 p-1 shadow-clay-soft backdrop-blur-sm">
                        {[
                            { value: 'monthly', labelKo: '월간', labelEn: 'Monthly' },
                            { value: 'yearly', labelKo: '연간 17% 절약', labelEn: 'Yearly, save 17%' },
                        ].map((option) => (
                            <button
                                key={option.value}
                                type="button"
                                data-testid={`pricing-billing-${option.value}`}
                                onClick={() => setBilling(option.value)}
                                className={[
                                    'rounded-[1rem] px-5 py-2 text-sm font-semibold transition-all duration-200',
                                    billing === option.value
                                        ? 'bg-gradient-to-r from-primary to-accent text-white shadow-clay-soft'
                                        : 'text-ink-muted hover:text-ink',
                                ].join(' ')}
                            >
                                {isKo ? option.labelKo : option.labelEn}
                            </button>
                        ))}
                    </div>

                    {checkoutError && (
                        <div
                            role="alert"
                            data-testid="pricing-checkout-error"
                            className="mx-auto mt-6 flex max-w-2xl items-start gap-3 rounded-[1rem] border border-red-200 bg-red-50/90 px-4 py-3 text-left text-sm leading-6 text-red-900 shadow-clay-soft"
                        >
                            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                            <span>{checkoutError}</span>
                        </div>
                    )}

                    {isCancelledCheckout && (
                        <div
                            role="status"
                            data-testid="pricing-checkout-cancelled"
                            className="mx-auto mt-6 flex max-w-2xl flex-col gap-4 rounded-[1rem] border border-amber-200 bg-amber-50/90 px-4 py-3 text-left text-sm leading-6 text-amber-950 shadow-clay-soft sm:flex-row sm:items-center sm:justify-between"
                        >
                            <div className="flex items-start gap-3">
                                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                                <span>
                                    <strong>Checkout canceled.</strong>{' '}
                                    {isKo
                                        ? `${cancelledTierName} ${cancelledBilling} 결제는 청구되지 않았습니다. 플랜을 조정하거나 준비되면 다시 시도하세요.`
                                        : `No charge was made for ${cancelledTierName} ${cancelledBilling}. Adjust your plan or try again when ready.`}
                                </span>
                            </div>
                            <button
                                type="button"
                                data-testid="pricing-checkout-cancelled-retry"
                                onClick={() => handleCheckout(cancelledPlan)}
                                disabled={loadingTier === cancelledPlan || cancelledPlan === currentTier}
                                className="clay-button clay-button-primary shrink-0 px-5 py-3 text-sm font-semibold text-white"
                            >
                                {loadingTier === cancelledPlan
                                    ? (isKo ? 'Processing...' : 'Processing...')
                                    : (isKo ? `Retry ${cancelledTierName}` : `Retry ${cancelledTierName}`)}
                            </button>
                        </div>
                    )}

                    {user && currentTier !== 'free' && (
                        <div
                            data-testid="pricing-manage-billing-panel"
                            className="mx-auto mt-6 flex max-w-2xl flex-col gap-4 rounded-[1rem] border border-white/60 bg-white/65 px-4 py-3 text-left text-sm leading-6 text-ink shadow-clay-soft sm:flex-row sm:items-center sm:justify-between"
                        >
                            <div className="flex items-start gap-3">
                                <CreditCard className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                                <span>
                                    <strong>{isKo ? 'Billing' : 'Billing'}:</strong>{' '}
                                    {isKo
                                        ? `${currentTier} plan is active.`
                                        : `${currentTier} plan is active.`}
                                </span>
                            </div>
                            <button
                                type="button"
                                data-testid="pricing-manage-billing"
                                onClick={handleManageBilling}
                                disabled={billingPortalLoading}
                                className="clay-button shrink-0 px-5 py-3 text-sm font-semibold text-ink"
                            >
                                {billingPortalLoading ? (isKo ? 'Opening...' : 'Opening...') : (isKo ? 'Manage billing' : 'Manage billing')}
                            </button>
                        </div>
                    )}
                </motion.div>

                <div className="grid gap-6 md:grid-cols-3">
                    {TIERS.map((tier, index) => {
                        const Icon = tier.icon;
                        const price = billing === 'monthly' ? tier.price.monthly : tier.price.yearly;
                        const isCurrent = currentTier === tier.id;
                        const isLoading = loadingTier === tier.id;
                        const isEnterpriseContact = tier.id === 'enterprise' && !isCurrent;
                        const ctaLabel = isLoading
                            ? (isKo ? '처리 중...' : 'Processing...')
                            : isCurrent
                                ? (isKo ? '현재 플랜' : 'Current plan')
                                : (isKo ? tier.ctaKo : tier.ctaEn);
                        const ctaClassName = [
                            'w-full rounded-[1.4rem] px-5 py-3.5 text-center text-sm font-semibold transition-all',
                            tier.popular
                                ? 'clay-button clay-button-primary text-white'
                                : isCurrent
                                    ? 'clay-panel-pressed cursor-default text-ink-soft'
                                    : 'clay-button text-ink',
                        ].join(' ');

                        return (
                            <motion.div
                                key={tier.id}
                                initial={{ opacity: 0, y: 30 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: index * 0.12, duration: 0.5 }}
                            >
                                <GlassCard className={`relative flex h-full flex-col p-7 transition-all ${tier.popular ? 'ring-2 ring-primary/40' : ''}`}>
                                    {tier.popular && (
                                        <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                                            <Badge variant="default" className="px-4 py-1 text-xs">
                                                {isKo ? '인기 플랜' : 'Most popular'}
                                            </Badge>
                                        </div>
                                    )}
                                    {isCurrent && (
                                        <div className="absolute right-4 top-4">
                                            <Badge variant="success">{isKo ? '현재' : 'Current'}</Badge>
                                        </div>
                                    )}

                                    <div className="mb-5">
                                        <div className="flex h-12 w-12 items-center justify-center rounded-[1.2rem] bg-white text-primary shadow-clay-soft">
                                            <Icon className="h-5 w-5" />
                                        </div>
                                        <h2 className="mt-3 font-display text-2xl font-semibold text-ink">
                                            {tier.name}
                                        </h2>
                                        <p className="mt-1 text-sm leading-6 text-ink-muted">
                                            {isKo ? tier.descKo : tier.descEn}
                                        </p>
                                    </div>

                                    <div className="mb-6 border-b border-white/30 pb-6">
                                        <span className="font-display text-5xl font-semibold text-ink">${price}</span>
                                        <span className="ml-1 text-sm text-ink-muted">
                                            /{billing === 'monthly' ? (isKo ? '월' : 'mo') : (isKo ? '년' : 'yr')}
                                        </span>
                                    </div>

                                    <ul className="mb-7 flex-1 space-y-3">
                                        {tier.features.map((feature) => (
                                            <li key={feature.textEn} className="flex items-center gap-3">
                                                <span className={[
                                                    'flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs',
                                                    feature.included ? 'bg-primary/15 text-primary' : 'bg-white/40 text-ink-soft',
                                                ].join(' ')}
                                                >
                                                    {feature.included ? <Check className="h-3 w-3" /> : <Minus className="h-3 w-3" />}
                                                </span>
                                                <span className={[
                                                    'text-sm',
                                                    feature.included ? 'text-ink' : 'text-ink-soft line-through',
                                                ].join(' ')}
                                                >
                                                    {isKo ? feature.textKo : feature.textEn}
                                                </span>
                                            </li>
                                        ))}
                                    </ul>

                                    {isEnterpriseContact ? (
                                        <a
                                            href={ENTERPRISE_CONTACT_HREF}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            data-testid={`pricing-${tier.id}-cta`}
                                            className={ctaClassName}
                                        >
                                            {ctaLabel}
                                        </a>
                                    ) : (
                                        <motion.button
                                            whileHover={{ scale: isCurrent ? 1 : 1.02 }}
                                            whileTap={{ scale: 0.98 }}
                                            type="button"
                                            data-testid={`pricing-${tier.id}-cta`}
                                            onClick={() => handleCheckout(tier.id)}
                                            disabled={isLoading || isCurrent}
                                            className={ctaClassName}
                                        >
                                            {ctaLabel}
                                        </motion.button>
                                    )}
                                </GlassCard>
                            </motion.div>
                        );
                    })}
                </div>

                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.6 }}
                    className="mt-10 flex flex-wrap items-center justify-center gap-6 text-sm text-ink-soft"
                >
                    <span className="flex items-center gap-2">
                        <Lock className="h-4 w-4" />
                        {isKo ? 'Stripe 보안 결제' : 'Secured by Stripe'}
                    </span>
                    <span className="flex items-center gap-2">
                        <Zap className="h-4 w-4" />
                        {isKo ? '언제든 취소 가능' : 'Cancel anytime'}
                    </span>
                    <span className="flex items-center gap-2">
                        <Building2 className="h-4 w-4" />
                        {isKo ? '7일 무료 체험' : '7-day free trial'}
                    </span>
                </motion.div>
            </div>
        </div>
    );
}
