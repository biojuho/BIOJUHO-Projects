import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion, useInView } from 'framer-motion';
import {
    ArrowRight,
    BookOpen,
    Brain,
    ChevronDown,
    CircleDollarSign,
    Dna,
    FlaskConical,
    Globe2,
    Lock,
    Scale,
    ShieldCheck,
    Sparkles,
    TrendingUp,
    Users,
    Zap,
} from 'lucide-react';
import { useLocale } from '../contexts/LocaleContext';
import { useDocumentMeta } from '../hooks/useDocumentMeta';
import LocaleToggle from './ui/LocaleToggle';

function AnimatedCounter({ end, suffix = '', duration = 2000 }) {
    const [value, setValue] = useState(0);
    const ref = useRef(null);
    const inView = useInView(ref, { once: true });

    useEffect(() => {
        if (!inView) return undefined;

        let frameId;
        const start = Date.now();
        const tick = () => {
            const elapsed = Date.now() - start;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - (1 - progress) ** 3;
            setValue(Math.floor(eased * end));
            if (progress < 1) {
                frameId = requestAnimationFrame(tick);
                return;
            }
            setValue(end);
        };

        frameId = requestAnimationFrame(tick);
        return () => cancelAnimationFrame(frameId);
    }, [inView, end, duration]);

    return <span ref={ref}>{value.toLocaleString()}{suffix}</span>;
}

const STATS = [
    { id: 'papers', value: 1240, suffix: '+', labelKo: '등록 논문', labelEn: 'Papers Indexed' },
    { id: 'vcs', value: 87, suffix: '', labelKo: '파트너 VC', labelEn: 'Partner VCs' },
    { id: 'grants', value: 430, suffix: '+', labelKo: '추적 공고', labelEn: 'Grants Tracked' },
    { id: 'reward', value: 52000, suffix: '+', labelKo: 'DSCI 보상', labelEn: 'DSCI Rewarded' },
];

const FEATURES = [
    {
        icon: Brain,
        colorClass: 'from-violet-500 to-purple-600',
        titleKo: 'AI 매칭 엔진',
        titleEn: 'AI Matching Engine',
        descKo: '논문, 기술 키워드, 공고 본문을 벡터 검색으로 연결해 가장 설득력 있는 지원 기회를 찾습니다.',
        descEn: 'Connect papers, technical keywords, and RFP text through vector search to surface the strongest funding fit.',
    },
    {
        icon: CircleDollarSign,
        colorClass: 'from-emerald-500 to-teal-600',
        titleKo: 'VC 딜플로우',
        titleEn: 'VC Deal Flow',
        descKo: '투자사별 논리와 선호 단계에 맞춰 연구 자산을 정렬하고, 왜 맞는지 설명합니다.',
        descEn: 'Rank research assets against each firm thesis and stage preference with explainable rationale.',
    },
    {
        icon: Dna,
        colorClass: 'from-sky-500 to-blue-600',
        titleKo: 'IPFS 영구 저장',
        titleEn: 'IPFS Permanent Storage',
        descKo: '논문과 기술 자산을 IPFS 기반 저장 흐름에 연결해 검증 가능한 연구 기록을 남깁니다.',
        descEn: 'Attach papers and technical assets to IPFS-based storage for verifiable scientific records.',
    },
    {
        icon: ShieldCheck,
        colorClass: 'from-amber-500 to-orange-600',
        titleKo: 'IP-NFT 민팅',
        titleEn: 'IP-NFT Minting',
        descKo: '연구 기여를 IP-NFT로 기록하고 보상, 소유권, 검토 이력을 하나의 신뢰 흐름으로 묶습니다.',
        descEn: 'Record research contributions as IP-NFTs and tie rewards, ownership, and review history together.',
    },
    {
        icon: Scale,
        colorClass: 'from-rose-500 to-pink-600',
        titleKo: '거버넌스 허브',
        titleEn: 'Governance Hub',
        descKo: '제안, 투표, 실행 상태를 투명하게 관리해 연구 커뮤니티의 의사결정을 운영합니다.',
        descEn: 'Manage proposals, voting, and execution states so the research community can govern transparently.',
    },
    {
        icon: Zap,
        colorClass: 'from-indigo-500 to-cyan-600',
        titleKo: 'AI 제안서 생성',
        titleEn: 'AI Proposal Generation',
        descKo: '매칭 결과에서 바로 제안서 초안과 리뷰 포인트를 생성해 작성 시간을 줄입니다.',
        descEn: 'Generate proposal drafts and review points directly from matching results to compress writing time.',
    },
];

const PERSONAS = [
    {
        icon: FlaskConical,
        roleKo: '연구자 / 포스트닥',
        roleEn: 'Researcher / Postdoc',
        painKo: '지원 공고 탐색과 제안서 초안 작성에 너무 많은 시간이 듭니다.',
        painEn: 'Grant search and proposal drafting consume too much research time.',
        gainKo: '논문 기반 매칭, 공고 탐색, 제안서 초안을 한 흐름에서 처리합니다.',
        gainEn: 'Run paper-based matching, funding discovery, and proposal drafts in one flow.',
        color: 'text-primary',
        bg: 'bg-primary/10',
    },
    {
        icon: TrendingUp,
        roleKo: 'VC 파트너 / 바이오 애널리스트',
        roleEn: 'VC Partner / Bio Analyst',
        painKo: '초기 연구 자산을 찾고 기술 적합도를 설명하는 데 시간이 오래 걸립니다.',
        painEn: 'Sourcing early research assets and explaining fit takes too long.',
        gainKo: '투자 논리에 맞는 연구 자산을 우선순위와 근거로 확인합니다.',
        gainEn: 'Review thesis-aligned assets with priority, fit score, and rationale.',
        color: 'text-accent',
        bg: 'bg-accent/10',
    },
];

const WORKFLOW = [
    {
        step: '01',
        titleKo: '논문 등록',
        titleEn: 'Upload Paper',
        descKo: 'PDF와 초록을 등록하고 IPFS/벡터 인덱싱 흐름을 시작합니다.',
        descEn: 'Register the PDF and abstract, then start IPFS and vector indexing.',
    },
    {
        step: '02',
        titleKo: 'AI 분석',
        titleEn: 'AI Analysis',
        descKo: '연구 내용과 공고 조건을 비교해 적합도와 보완점을 계산합니다.',
        descEn: 'Compare research content with opportunity requirements and surface gaps.',
    },
    {
        step: '03',
        titleKo: '투자자 매칭',
        titleEn: 'VC Matching',
        descKo: 'VC별 투자 논리에 맞는 자산을 정렬하고 설명 가능한 딜플로우를 만듭니다.',
        descEn: 'Rank assets against VC theses and produce explainable deal flow.',
    },
    {
        step: '04',
        titleKo: '보상과 거버넌스',
        titleEn: 'Rewards and Governance',
        descKo: 'DSCI 보상, 리뷰, 제안, 투표를 신뢰 레이어로 연결합니다.',
        descEn: 'Connect DSCI rewards, reviews, proposals, and votes into a trust layer.',
    },
];

const cardVariants = {
    hidden: { opacity: 0, y: 32 },
    visible: (index) => ({
        opacity: 1,
        y: 0,
        transition: { delay: index * 0.08, duration: 0.5, ease: [0.2, 0.9, 0.2, 1] },
    }),
};

export default function LandingPage() {
    const { locale } = useLocale();
    const isKo = locale === 'ko-KR';
    useDocumentMeta({
        title: isKo
            ? 'DecentBio — 바이오 연구를 AI로 가속화하는 DeSci 플랫폼'
            : 'DecentBio — AI-Powered DeSci Platform for Bio Research',
        description: isKo
            ? '정부과제 매칭, VC 연결, AI 제안서 생성, IPFS 논문 저장을 한 곳에서.'
            : 'Grant matching, VC connections, AI proposals, and IPFS paper storage in one place.',
        canonicalPath: '/',
    });
    const featuresRef = useRef(null);
    const featuresInView = useInView(featuresRef, { once: true, margin: '-80px' });

    const scrollToFeatures = () => featuresRef.current?.scrollIntoView({ behavior: 'smooth' });

    return (
        <div className="relative min-h-screen overflow-x-hidden" style={{ background: 'var(--bg-primary, #f0ece6)' }}>
            <div className="ambient-bg" aria-hidden="true" />

            {/* Scientific Generative Bio-Mesh SVG Overlay */}
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-7xl h-[700px] overflow-hidden pointer-events-none z-0 opacity-60 select-none" aria-hidden="true">
                <svg className="w-full h-full min-w-[1024px]" viewBox="0 0 1200 700" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <defs>
                        <radialGradient id="mesh-glow-left" cx="20%" cy="40%" r="30%">
                            <stop offset="0%" stopColor="#10b981" stopOpacity="0.12" />
                            <stop offset="100%" stopColor="#10b981" stopOpacity="0" />
                        </radialGradient>
                        <radialGradient id="mesh-glow-right" cx="80%" cy="30%" r="30%">
                            <stop offset="0%" stopColor="#6366f1" stopOpacity="0.12" />
                            <stop offset="100%" stopColor="#6366f1" stopOpacity="0" />
                        </radialGradient>
                        <linearGradient id="helix-line-grad" x1="0" y1="0" x2="1" y2="1">
                            <stop offset="0%" stopColor="#10b981" stopOpacity="0.2" />
                            <stop offset="50%" stopColor="#6366f1" stopOpacity="0.15" />
                            <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.05" />
                        </linearGradient>
                    </defs>

                    {/* Background Soft Glows */}
                    <rect width="100%" height="100%" fill="url(#mesh-glow-left)" />
                    <rect width="100%" height="100%" fill="url(#mesh-glow-right)" />

                    {/* Scientific Molecular Connections & DNA Helix Representation */}
                    <g className="animate-pulse-slow">
                        {/* Connected Node Lines (Left Web) */}
                        <line x1="120" y1="200" x2="220" y2="150" stroke="url(#helix-line-grad)" strokeWidth="1" strokeDasharray="3 3" />
                        <line x1="220" y1="150" x2="280" y2="280" stroke="url(#helix-line-grad)" strokeWidth="1" />
                        <line x1="120" y1="200" x2="280" y2="280" stroke="url(#helix-line-grad)" strokeWidth="1.5" />
                        <line x1="280" y1="280" x2="200" y2="380" stroke="url(#helix-line-grad)" strokeWidth="1" strokeDasharray="4 2" />
                        <line x1="200" y1="380" x2="120" y2="200" stroke="url(#helix-line-grad)" strokeWidth="1" />

                        {/* Left Web Nodes */}
                        <circle cx="120" cy="200" r="5" fill="#10b981" className="animate-float-gentle" />
                        <circle cx="220" cy="150" r="3" fill="#6366f1" />
                        <circle cx="280" cy="280" r="6" fill="#8b5cf6" className="animate-float-slower" />
                        <circle cx="200" cy="380" r="4" fill="#10b981" />

                        {/* Dotted orbital rings to imply planetary or electron shells */}
                        <circle cx="280" cy="280" r="45" stroke="#8b5cf6" strokeWidth="0.75" strokeDasharray="3 6" strokeOpacity="0.4" />
                        <circle cx="120" cy="200" r="30" stroke="#10b981" strokeWidth="0.75" strokeDasharray="2 4" strokeOpacity="0.4" />
                    </g>

                    <g className="animate-pulse-slow-reverse">
                        {/* Connected Node Lines (Right Web) */}
                        <line x1="1080" y1="180" x2="980" y2="280" stroke="url(#helix-line-grad)" strokeWidth="1" />
                        <line x1="980" y1="280" x2="920" y2="150" stroke="url(#helix-line-grad)" strokeWidth="1.5" strokeDasharray="4 4" />
                        <line x1="920" y1="150" x2="1080" y2="180" stroke="url(#helix-line-grad)" strokeWidth="1" />
                        <line x1="980" y1="280" x2="1020" y2="390" stroke="url(#helix-line-grad)" strokeWidth="1" />
                        <line x1="1020" y1="390" x2="1080" y2="180" stroke="url(#helix-line-grad)" strokeWidth="1.2" strokeDasharray="2 2" />

                        {/* Right Web Nodes */}
                        <circle cx="1080" cy="180" r="4" fill="#6366f1" />
                        <circle cx="980" cy="280" r="6" fill="#10b981" className="animate-float-slower" />
                        <circle cx="920" cy="150" r="3" fill="#8b5cf6" />
                        <circle cx="1020" cy="390" r="5" fill="#6366f1" className="animate-float-gentle" />

                        <circle cx="980" cy="280" r="50" stroke="#10b981" strokeWidth="0.75" strokeDasharray="4 5" strokeOpacity="0.4" />
                    </g>

                    {/* DNA Double Helix Representation running across behind the central title */}
                    <g className="opacity-25">
                        {/* Strand A */}
                        <path d="M 300 220 Q 375 120 450 220 T 600 220 T 750 220 T 900 220" fill="none" stroke="url(#helix-line-grad)" strokeWidth="2" strokeDasharray="6 3" />
                        {/* Strand B */}
                        <path d="M 300 220 Q 375 320 450 220 T 600 220 T 750 220 T 900 220" fill="none" stroke="url(#helix-line-grad)" strokeWidth="2" />

                        {/* Connecting base-pair rungs */}
                        <line x1="337" y1="180" x2="337" y2="260" stroke="#10b981" strokeWidth="1" strokeOpacity="0.5" />
                        <line x1="412" y1="180" x2="412" y2="260" stroke="#6366f1" strokeWidth="1" strokeOpacity="0.5" />

                        <line x1="487" y1="260" x2="487" y2="180" stroke="#8b5cf6" strokeWidth="1" strokeOpacity="0.5" />
                        <line x1="562" y1="260" x2="562" y2="180" stroke="#10b981" strokeWidth="1" strokeOpacity="0.5" />

                        <line x1="637" y1="180" x2="637" y2="260" stroke="#6366f1" strokeWidth="1" strokeOpacity="0.5" />
                        <line x1="712" y1="180" x2="712" y2="260" stroke="#8b5cf6" strokeWidth="1" strokeOpacity="0.5" />

                        <line x1="787" y1="260" x2="787" y2="180" stroke="#10b981" strokeWidth="1" strokeOpacity="0.5" />
                        <line x1="862" y1="260" x2="862" y2="180" stroke="#6366f1" strokeWidth="1" strokeOpacity="0.5" />
                    </g>
                </svg>
            </div>

            <nav className="relative z-20 flex items-center justify-between px-6 py-5 lg:px-12">
                <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-[1.2rem] bg-gradient-to-br from-primary to-accent text-white shadow-clay-soft">
                        <Sparkles className="h-5 w-5" />
                    </div>
                    <span className="font-display text-2xl font-semibold text-ink">DSCI</span>
                </div>
                <div className="flex items-center gap-3">
                    <LocaleToggle />
                    <Link to="/login" className="clay-button text-sm font-semibold text-ink-muted hover:text-ink" data-testid="landing-sign-in">
                        {isKo ? '로그인' : 'Sign in'}
                    </Link>
                    <Link to="/login?next=/dashboard" className="clay-button clay-button-primary text-sm font-semibold text-white" data-testid="landing-header-get-started">
                        {isKo ? '무료로 시작' : 'Get started free'}
                        <ArrowRight className="h-4 w-4" />
                    </Link>
                </div>
            </nav>

            <section className="relative z-10 mx-auto max-w-7xl px-6 pb-16 pt-12 lg:px-12 lg:pt-20">
                <motion.div
                    initial={{ opacity: 0, y: 24 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.65, ease: [0.2, 0.9, 0.2, 1] }}
                    className="text-center"
                >
                    <span className="clay-chip mb-6 inline-block">
                        {isKo ? '탈중앙 과학 마켓플레이스' : 'Decentralized Science Marketplace'}
                    </span>
                    <h1 className="mx-auto max-w-5xl font-display text-[clamp(2.8rem,7vw,5.5rem)] font-semibold leading-[0.96] text-ink">
                        {isKo ? (
                            <>연구와 자본이<br /><span className="text-gradient">같은 화면에서 만납니다</span></>
                        ) : (
                            <>Where researchers and capital<br /><span className="text-gradient">meet on one surface</span></>
                        )}
                    </h1>
                    <p className="mx-auto mt-6 max-w-2xl text-lg leading-8 text-ink-muted">
                        {isKo
                            ? 'AI 매칭, IPFS 저장, 투자자 딜플로우, 거버넌스를 하나의 제품 흐름으로 연결합니다.'
                            : 'AI matching, IPFS storage, investor deal flow, and governance connected as one product flow.'}
                    </p>
                    <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
                        <Link to="/login?next=/upload" className="clay-button clay-button-primary px-8 py-4 text-base font-semibold text-white" data-testid="landing-start-researcher">
                            <FlaskConical className="h-5 w-5" />
                            {isKo ? '연구자로 시작하기' : 'Start as Researcher'}
                            <ArrowRight className="h-4 w-4" />
                        </Link>
                        <Link to="/explore" className="clay-button px-8 py-4 text-base font-semibold text-ink" data-testid="landing-explore-research">
                            <BookOpen className="h-5 w-5" />
                            {isKo ? '공개 연구 보기' : 'Explore Research'}
                        </Link>
                    </div>
                    <button
                        type="button"
                        onClick={scrollToFeatures}
                        className="mx-auto mt-12 flex flex-col items-center gap-2 text-sm text-ink-soft transition-opacity hover:opacity-70"
                        aria-label={isKo ? '기능 섹션으로 이동' : 'Scroll to features'}
                    >
                        <span>{isKo ? '기능 살펴보기' : 'See features'}</span>
                        <ChevronDown className="h-5 w-5 animate-bounce" />
                    </button>
                </motion.div>

                <motion.div
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3, duration: 0.6 }}
                    className="mx-auto mt-16 grid max-w-4xl grid-cols-2 gap-4 md:grid-cols-4"
                >
                    {STATS.map((stat) => (
                        <div key={stat.id} className="glass-card p-5 text-center">
                            <p className="font-display text-3xl font-semibold text-ink">
                                <AnimatedCounter end={stat.value} suffix={stat.suffix} />
                            </p>
                            <p className="mt-2 text-xs font-semibold uppercase tracking-wider text-ink-soft">
                                {isKo ? stat.labelKo : stat.labelEn}
                            </p>
                        </div>
                    ))}
                </motion.div>
            </section>

            <section className="relative z-10 mx-auto max-w-7xl px-6 py-16 lg:px-12">
                <div className="mb-10 text-center">
                    <p className="clay-chip mb-3 inline-block">
                        {isKo ? '두 사용자를 위한 제품' : 'Built for two personas'}
                    </p>
                    <h2 className="font-display text-3xl font-semibold text-ink">
                        {isKo ? '연구자와 투자자를 잇는 마켓플레이스' : 'A marketplace for researchers and investors'}
                    </h2>
                </div>
                <div className="grid gap-6 md:grid-cols-2">
                    {PERSONAS.map((persona) => {
                        const Icon = persona.icon;
                        return (
                            <motion.div
                                key={persona.roleEn}
                                initial={{ opacity: 0, x: -16 }}
                                whileInView={{ opacity: 1, x: 0 }}
                                viewport={{ once: true }}
                                transition={{ duration: 0.5 }}
                                className="glass-card p-8"
                            >
                                <div className={`mb-5 inline-flex h-14 w-14 items-center justify-center rounded-[1.4rem] ${persona.bg} ${persona.color}`}>
                                    <Icon className="h-7 w-7" />
                                </div>
                                <h3 className="mb-2 font-display text-xl font-semibold text-ink">
                                    {isKo ? persona.roleKo : persona.roleEn}
                                </h3>
                                <div className="space-y-3">
                                    <div className="clay-panel-pressed rounded-[1.4rem] p-4">
                                        <p className="mb-1 text-[10px] font-bold uppercase tracking-wider text-ink-soft">
                                            {isKo ? '불편함' : 'Pain point'}
                                        </p>
                                        <p className="text-sm text-ink-muted">
                                            {isKo ? persona.painKo : persona.painEn}
                                        </p>
                                    </div>
                                    <div className="clay-panel-pressed rounded-[1.4rem] p-4">
                                        <p className="mb-1 text-[10px] font-bold uppercase tracking-wider text-primary">
                                            {isKo ? 'DSCI로 해결' : 'With DSCI'}
                                        </p>
                                        <p className="text-sm font-semibold text-ink">
                                            {isKo ? persona.gainKo : persona.gainEn}
                                        </p>
                                    </div>
                                </div>
                            </motion.div>
                        );
                    })}
                </div>
            </section>

            <section ref={featuresRef} className="relative z-10 mx-auto max-w-7xl px-6 py-16 lg:px-12">
                <div className="mb-12 text-center">
                    <p className="clay-chip mb-3 inline-block">
                        {isKo ? '핵심 기능' : 'Core features'}
                    </p>
                    <h2 className="font-display text-4xl font-semibold text-ink">
                        {isKo ? '하나의 플랫폼, 전체 파이프라인' : 'One platform, full pipeline'}
                    </h2>
                    <p className="mx-auto mt-4 max-w-2xl text-base text-ink-muted">
                        {isKo
                            ? '논문 제출부터 투자자 매칭, 제안서, 거버넌스까지 연구 사업화의 핵심 흐름을 연결합니다.'
                            : 'From paper submission to investor matching, proposal drafting, and governance, DSCI connects the operating flow.'}
                    </p>
                </div>
                <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
                    {FEATURES.map((feature, index) => {
                        const Icon = feature.icon;
                        return (
                            <motion.div
                                key={feature.titleEn}
                                custom={index}
                                variants={cardVariants}
                                initial="hidden"
                                animate={featuresInView ? 'visible' : 'hidden'}
                                className="glass-card p-6 transition-all hover:-translate-y-1"
                            >
                                <div className={`mb-5 inline-flex h-12 w-12 items-center justify-center rounded-[1.2rem] bg-gradient-to-br ${feature.colorClass} text-white shadow-clay-soft`}>
                                    <Icon className="h-5 w-5" />
                                </div>
                                <h3 className="mb-2 font-display text-lg font-semibold text-ink">
                                    {isKo ? feature.titleKo : feature.titleEn}
                                </h3>
                                <p className="text-sm leading-7 text-ink-muted">
                                    {isKo ? feature.descKo : feature.descEn}
                                </p>
                            </motion.div>
                        );
                    })}
                </div>
            </section>

            <section className="relative z-10 mx-auto max-w-7xl px-6 py-16 lg:px-12">
                <div className="mb-12 text-center">
                    <p className="clay-chip mb-3 inline-block">{isKo ? '4단계 파이프라인' : '4-step pipeline'}</p>
                    <h2 className="font-display text-4xl font-semibold text-ink">
                        {isKo ? '등록부터 보상까지 연결된 흐름' : 'A connected flow from upload to reward'}
                    </h2>
                </div>
                <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-4">
                    {WORKFLOW.map((step, index) => (
                        <motion.div
                            key={step.step}
                            initial={{ opacity: 0, y: 24 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ delay: index * 0.1, duration: 0.5 }}
                            className="glass-card p-6"
                        >
                            <span className="font-display text-5xl font-semibold text-primary/20">{step.step}</span>
                            <h3 className="mt-3 font-display text-xl font-semibold text-ink">
                                {isKo ? step.titleKo : step.titleEn}
                            </h3>
                            <p className="mt-2 text-sm leading-7 text-ink-muted">
                                {isKo ? step.descKo : step.descEn}
                            </p>
                        </motion.div>
                    ))}
                </div>
            </section>

            <section className="relative z-10 mx-auto max-w-7xl px-6 py-16 lg:px-12">
                <motion.div
                    initial={{ opacity: 0, scale: 0.97 }}
                    whileInView={{ opacity: 1, scale: 1 }}
                    viewport={{ once: true }}
                    className="glass-card overflow-hidden p-10 text-center md:p-16"
                >
                    <p className="clay-chip mb-4 inline-block">
                        {isKo ? '지금 무료로 시작하세요' : 'Start for free today'}
                    </p>
                    <h2 className="font-display text-4xl font-semibold text-ink md:text-5xl">
                        {isKo ? '연구가 자본을 만나는 순간' : 'The moment research meets capital'}
                    </h2>
                    <p className="mx-auto mt-4 max-w-xl text-base leading-7 text-ink-muted">
                        {isKo
                            ? '무료 계정으로 논문 등록, 공고 탐색, AI 매칭 흐름을 바로 확인하세요.'
                            : 'Create a free account to try paper submission, funding discovery, and AI matching.'}
                    </p>
                    <div className="mt-8 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
                        <Link to="/login?next=/dashboard" className="clay-button clay-button-primary px-10 py-4 text-base font-semibold text-white" data-testid="landing-create-account">
                            <Sparkles className="h-5 w-5" />
                            {isKo ? '무료 계정 만들기' : 'Create free account'}
                            <ArrowRight className="h-4 w-4" />
                        </Link>
                        <Link to="/pricing" className="clay-button px-10 py-4 text-base font-semibold text-ink" data-testid="landing-compare-plans">
                            {isKo ? '요금제 비교' : 'Compare plans'}
                        </Link>
                    </div>
                    <div className="mt-6 flex flex-wrap items-center justify-center gap-6 text-sm text-ink-soft">
                        <span className="flex items-center gap-1.5">
                            <Lock className="h-3.5 w-3.5" />
                            {isKo ? '신용카드 불필요' : 'No credit card'}
                        </span>
                        <span className="flex items-center gap-1.5">
                            <Globe2 className="h-3.5 w-3.5" />
                            {isKo ? 'IPFS 저장 흐름' : 'IPFS storage flow'}
                        </span>
                        <span className="flex items-center gap-1.5">
                            <Users className="h-3.5 w-3.5" />
                            {isKo ? '커뮤니티 거버넌스' : 'Community governed'}
                        </span>
                    </div>
                </motion.div>
            </section>

            <footer className="relative z-10 border-t border-white/20 px-6 py-8 lg:px-12">
                <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 md:flex-row">
                    <div className="flex items-center gap-3">
                        <div className="flex h-8 w-8 items-center justify-center rounded-[0.9rem] bg-gradient-to-br from-primary to-accent text-white">
                            <Sparkles className="h-4 w-4" />
                        </div>
                        <span className="font-display text-lg font-semibold text-ink">DSCI</span>
                    </div>
                    <p className="text-sm text-ink-soft">
                        {isKo
                            ? 'DSCI - 연구자와 자본을 연결하는 탈중앙 과학 마켓플레이스. (c) 2026 Built by Raph & JuPark'
                            : 'DSCI - the decentralized science marketplace. (c) 2026 Built by Raph & JuPark'}
                    </p>
                    <div className="flex items-center gap-4 text-sm text-ink-muted">
                        <Link to="/pricing" className="hover:text-ink">
                            {isKo ? '요금제' : 'Pricing'}
                        </Link>
                        <Link to="/login" className="hover:text-ink">
                            {isKo ? '로그인' : 'Sign in'}
                        </Link>
                        <Link to="/explore" className="hover:text-ink">
                            {isKo ? '연구 탐색' : 'Explore'}
                        </Link>
                    </div>
                </div>
            </footer>
        </div>
    );
}
