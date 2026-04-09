/**
 * PricingPage — DeSci Platform Pricing & Subscription
 * Glassmorphism 3-tier pricing cards with Stripe Checkout integration.
 */
import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useAuth } from '../contexts/AuthContext';
import api from '../services/api';

const TIERS = [
  {
    id: 'free',
    name: 'Starter',
    price: { monthly: 0, yearly: 0 },
    description: '연구 탐색을 시작하는 분들을 위한 무료 플랜',
    features: [
      { text: '정부과제 검색 월 10건', included: true },
      { text: 'AI 적합도 분석 월 3건', included: true },
      { text: 'IPFS 논문 저장 3편', included: true },
      { text: 'VC 매칭 결과 보기', included: true },
      { text: 'DSCI 토큰 기본 보상', included: true },
      { text: 'AI 제안서 자동 생성', included: false },
      { text: '문헌 리뷰', included: false },
    ],
    cta: '현재 플랜',
    color: 'from-slate-500/20 to-slate-600/10',
    border: 'border-white/10',
    icon: '🧪',
  },
  {
    id: 'pro',
    name: 'Pro',
    price: { monthly: 29, yearly: 290 },
    description: '본격적인 연구와 사업화를 위한 프로 플랜',
    popular: true,
    features: [
      { text: '정부과제 검색 무제한', included: true },
      { text: 'AI 적합도 분석 월 30건', included: true },
      { text: 'AI 제안서 자동 생성 월 5건', included: true },
      { text: 'VC 매칭 + 연락처 포함', included: true },
      { text: 'IPFS 논문 저장 30편', included: true },
      { text: '문헌 리뷰 월 10건', included: true },
      { text: 'DSCI 토큰 2x 보상', included: true },
    ],
    cta: '업그레이드',
    color: 'from-emerald-500/20 to-teal-600/15',
    border: 'border-emerald-400/30',
    icon: '🔬',
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    price: { monthly: 199, yearly: 1990 },
    description: '기관 및 기업을 위한 엔터프라이즈 플랜',
    features: [
      { text: '모든 기능 무제한', included: true },
      { text: '맞춤형 AI 제안서', included: true },
      { text: '전담 매니저', included: true },
      { text: '우선 기술 지원', included: true },
      { text: '커스텀 DSCI 보상', included: true },
      { text: 'API 액세스 (120 req/min)', included: true },
      { text: '온프레미스 배포 지원', included: true },
    ],
    cta: '문의하기',
    color: 'from-violet-500/20 to-purple-600/15',
    border: 'border-violet-400/20',
    icon: '🏢',
  },
];

export default function PricingPage() {
  const { user } = useAuth();
  const [billing, setBilling] = useState('monthly');
  const [loadingTier, setLoadingTier] = useState(null);
  const [currentTier, setCurrentTier] = useState('free');

  useEffect(() => {
    if (!user) {
      setCurrentTier('free');
      return;
    }

    api.get('/subscription/tier')
      .then((response) => setCurrentTier(response.data?.tier || 'free'))
      .catch(() => {});
  }, [user]);

  const handleCheckout = async (tierId) => {
    if (tierId === 'free' || tierId === currentTier) return;

    if (tierId === 'enterprise') {
      window.open('mailto:hello@decentbio.xyz?subject=Enterprise Plan Inquiry', '_blank');
      return;
    }

    setLoadingTier(tierId);
    try {
      const { data } = await api.post('/subscription/checkout', { tier: tierId, billing });
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
      }
    } catch (err) {
      console.error('Checkout error:', err);
    } finally {
      setLoadingTier(null);
    }
  };

  return (
    <div style={{ minHeight: '100vh', padding: '2rem', background: 'var(--bg-primary, #0a0a1a)' }}>
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        style={{ textAlign: 'center', marginBottom: '3rem' }}
      >
        <h1 style={{
          fontSize: '2.5rem',
          fontWeight: 800,
          background: 'linear-gradient(135deg, #4ade80, #06b6d4, #a78bfa)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          marginBottom: '1rem',
        }}>
          연구를 가속화할 플랜을 선택하세요
        </h1>
        <p style={{ color: 'rgba(255,255,255,0.6)', fontSize: '1.1rem', maxWidth: 600, margin: '0 auto' }}>
          DeSci 플랫폼으로 바이오 연구, 정부과제, VC 매칭을 AI로 혁신하세요.
        </p>

        {/* Billing toggle */}
        <div style={{
          display: 'inline-flex',
          marginTop: '2rem',
          padding: '4px',
          borderRadius: '12px',
          background: 'rgba(255,255,255,0.05)',
          border: '1px solid rgba(255,255,255,0.1)',
        }}>
          {['monthly', 'yearly'].map((b) => (
            <button
              key={b}
              onClick={() => setBilling(b)}
              style={{
                padding: '0.5rem 1.5rem',
                borderRadius: '10px',
                border: 'none',
                cursor: 'pointer',
                fontSize: '0.9rem',
                fontWeight: 600,
                transition: 'all 0.3s',
                background: billing === b
                  ? 'linear-gradient(135deg, #4ade80, #06b6d4)'
                  : 'transparent',
                color: billing === b ? '#000' : 'rgba(255,255,255,0.5)',
              }}
            >
              {b === 'monthly' ? '월간' : '연간 (17% 할인)'}
            </button>
          ))}
        </div>
      </motion.div>

      {/* Cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
        gap: '2rem',
        maxWidth: '1100px',
        margin: '0 auto',
      }}>
        {TIERS.map((tier, idx) => (
          <motion.div
            key={tier.id}
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.15, duration: 0.5 }}
            style={{
              position: 'relative',
              padding: '2rem',
              borderRadius: '20px',
              background: 'rgba(255,255,255,0.04)',
              backdropFilter: 'blur(24px)',
              border: tier.popular
                ? '2px solid rgba(74, 222, 128, 0.4)'
                : '1px solid rgba(255,255,255,0.08)',
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            {/* Popular badge */}
            {tier.popular && (
              <div style={{
                position: 'absolute',
                top: 0, right: 0,
                padding: '4px 16px',
                background: 'linear-gradient(135deg, #4ade80, #06b6d4)',
                borderRadius: '0 18px 0 12px',
                fontSize: '0.75rem',
                fontWeight: 700,
                color: '#000',
              }}>
                인기
              </div>
            )}

            {/* Current badge */}
            {currentTier === tier.id && (
              <div style={{
                position: 'absolute',
                top: 0, left: 0,
                padding: '4px 12px',
                background: 'rgba(255,255,255,0.15)',
                borderRadius: '0 0 12px 0',
                fontSize: '0.7rem',
                fontWeight: 600,
                color: 'rgba(255,255,255,0.7)',
              }}>
                현재 플랜
              </div>
            )}

            <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>{tier.icon}</div>
            <h3 style={{
              fontSize: '1.4rem',
              fontWeight: 700,
              color: '#fff',
              marginBottom: '0.3rem',
            }}>
              {tier.name}
            </h3>
            <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.85rem', marginBottom: '1.5rem' }}>
              {tier.description}
            </p>

            {/* Price */}
            <div style={{ marginBottom: '1.5rem' }}>
              <span style={{ fontSize: '2.8rem', fontWeight: 800, color: '#fff' }}>
                ${billing === 'monthly' ? tier.price.monthly : tier.price.yearly}
              </span>
              <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.9rem' }}>
                /{billing === 'monthly' ? '월' : '년'}
              </span>
            </div>

            {/* Features */}
            <ul style={{ listStyle: 'none', padding: 0, flex: 1, marginBottom: '1.5rem' }}>
              {tier.features.map((f, i) => (
                <li key={i} style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  padding: '0.4rem 0',
                  color: f.included ? 'rgba(255,255,255,0.8)' : 'rgba(255,255,255,0.25)',
                  fontSize: '0.9rem',
                }}>
                  <span style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: '18px',
                    height: '18px',
                    borderRadius: '50%',
                    fontSize: '0.7rem',
                    background: f.included ? 'rgba(74,222,128,0.2)' : 'rgba(255,255,255,0.05)',
                    color: f.included ? '#4ade80' : 'rgba(255,255,255,0.2)',
                    flexShrink: 0,
                  }}>
                    {f.included ? '✓' : '—'}
                  </span>
                  {f.text}
                </li>
              ))}
            </ul>

            {/* CTA */}
            <motion.button
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => handleCheckout(tier.id)}
              disabled={loadingTier === tier.id || currentTier === tier.id}
              style={{
                width: '100%',
                padding: '0.9rem',
                borderRadius: '12px',
                border: 'none',
                cursor: currentTier === tier.id ? 'default' : 'pointer',
                fontSize: '1rem',
                fontWeight: 700,
                transition: 'all 0.3s',
                background: tier.popular
                  ? 'linear-gradient(135deg, #4ade80, #06b6d4)'
                  : currentTier === tier.id
                    ? 'rgba(255,255,255,0.05)'
                    : 'rgba(255,255,255,0.1)',
                color: tier.popular ? '#000' : '#fff',
                opacity: currentTier === tier.id ? 0.5 : 1,
              }}
            >
              {loadingTier === tier.id
                ? '처리 중...'
                : currentTier === tier.id
                  ? '현재 플랜'
                  : tier.cta}
            </motion.button>
          </motion.div>
        ))}
      </div>

      {/* FAQ / Trust */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.8 }}
        style={{
          textAlign: 'center',
          marginTop: '3rem',
          color: 'rgba(255,255,255,0.3)',
          fontSize: '0.85rem',
        }}
      >
        <p>🔒 Stripe으로 안전하게 결제됩니다 ∙ 언제든 해지 가능 ∙ 7일 무료 체험</p>
      </motion.div>
    </div>
  );
}
