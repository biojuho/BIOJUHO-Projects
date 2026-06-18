import { useState, useMemo, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
    ArrowRight,
    BookOpen,
    Clock,
    ExternalLink,
    Filter,
    Search,
    Sparkles,
    Tag,
    User,
    ShieldCheck,
    Globe,
    Activity,
} from 'lucide-react';
import { useLocale } from '../contexts/LocaleContext';
import { useDocumentMeta } from '../hooks/useDocumentMeta';
import LocaleToggle from './ui/LocaleToggle';
import GlassCard from './ui/GlassCard';
import { Badge } from './ui/Badge';

const MOCK_PAPERS = [
    {
        id: '1',
        title: 'CRISPR-Cas9 Mediated Gene Correction in Sickle Cell Disease: A Phase I Clinical Trial Overview',
        authors: 'Park J., Kim S., Lee H.',
        abstract: 'We present preliminary results from a Phase I open-label trial using ex vivo CRISPR-Cas9 to restore HBB gene function in patients with sickle cell disease. 12-month follow-up data shows 87% reduction in vaso-occlusive episodes with no off-target effects detected.',
        tags: ['CRISPR', 'Gene Therapy', 'Sickle Cell', 'Clinical Trial'],
        ipfs_cid: 'QmXoYGnpFjy5F2zRRMRK9q8XqFhT5gE1sJaJ2Q5Nc9X1bK',
        date: '2026-03-15',
        field: 'Gene Therapy',
        cited: 23,
    },
    {
        id: '2',
        title: 'AI-Driven Drug Repurposing: Identifying Novel Alzheimer\'s Targets via Multi-Modal Graph Neural Networks',
        authors: 'Choi M., Raph R., Zhang W.',
        abstract: 'A graph neural network trained on 2.4M protein-drug interactions identifies 14 candidate compounds for Alzheimer\'s disease repurposing. Top-3 candidates validated in iPSC-derived neuronal models show more than 60% reduction in tau phosphorylation.',
        tags: ['Drug Discovery', 'GNN', 'Alzheimer\'s', 'AI/ML'],
        ipfs_cid: 'QmYoZGnpGjy6G3sSSMRL10q9YqGhU6hF2sKbK3R6Od2X2cL',
        date: '2026-02-28',
        field: 'AI Drug Discovery',
        cited: 41,
    },
    {
        id: '3',
        title: 'Decentralized Clinical Trial Infrastructure: IPFS + Smart Contracts for Consent Management',
        authors: 'Kim T., Santos A., Park B.',
        abstract: 'We propose a DeSci framework combining IPFS for immutable data storage with ERC-2535 Diamond proxies for upgradeable consent logic. A pilot with 450 participants demonstrates 99.3% data integrity and GDPR compliance without centralized servers.',
        tags: ['DeSci', 'IPFS', 'Clinical Trials', 'Smart Contracts'],
        ipfs_cid: 'QmZpAHopHky7H4tTTNSM11r0ZrHiV7iG3tLcL4S7Pe3Y3dM',
        date: '2026-01-20',
        field: 'DeSci Infrastructure',
        cited: 67,
    },
    {
        id: '4',
        title: 'Microbiome-Immune Axis in Pancreatic Cancer: A Multi-Center Cohort Analysis',
        authors: 'Lee Y., Yamamoto K., Hwang S.',
        abstract: 'Prospective cohort data from 1,200 pancreatic cancer patients suggests Fusobacterium nucleatum abundance as an independent predictor of chemotherapy resistance. Bacteriophage-based depletion restores sensitivity in patient-derived organoids.',
        tags: ['Microbiome', 'Pancreatic Cancer', 'Immunology', 'Oncology'],
        ipfs_cid: 'QmApBIqpIlz8I5uUUOTN22s1AsIjW8jH4uMdM5T8Qf4Z4eN',
        date: '2026-04-02',
        field: 'Oncology',
        cited: 18,
    },
    {
        id: '5',
        title: 'Quantum Error Correction in Biological Computing: Membrane Protein Simulations at Scale',
        authors: 'Roh J., Müller D., Nakamura Y.',
        abstract: 'Using quantum annealing workflows, we simulate KcsA potassium channel gating with sub-Angstrom accuracy. Error mitigation reduces simulation cost by 40% versus classical molecular dynamics.',
        tags: ['Quantum Computing', 'Biophysics', 'Drug Screening', 'Protein Simulation'],
        ipfs_cid: 'QmBqCJrqJma9J6vVVPUN33t2BtJkX9kI5vNeN6U9Rg5A5fO',
        date: '2026-04-10',
        field: 'Quantum Biology',
        cited: 9,
    },
    {
        id: '6',
        title: 'Federated Learning for Rare Disease Genomics: Privacy-Preserving Multi-Hospital GWAS',
        authors: 'Jung H., Garcia F., Lindström E.',
        abstract: 'Federated GWAS across 18 hospitals discovers seven novel rare-disease loci without sharing raw genotype data. Differential privacy preserves most statistical power compared with centralized analysis.',
        tags: ['Federated Learning', 'Genomics', 'GWAS', 'Privacy'],
        ipfs_cid: 'QmCrDKsrKnb0K7wWQVPO44u3CuKlY0lJ6wOfO7V0Sh6B6gP',
        date: '2026-03-28',
        field: 'Genomics',
        cited: 35,
    },
];

const ALL_FIELDS = ['All', 'Gene Therapy', 'AI Drug Discovery', 'DeSci Infrastructure', 'Oncology', 'Quantum Biology', 'Genomics'];

const FIELD_LABELS_KO = {
    All: '전체',
    'Gene Therapy': '유전자 치료',
    'AI Drug Discovery': 'AI 신약개발',
    'DeSci Infrastructure': 'DeSci 인프라',
    Oncology: '종양학',
    'Quantum Biology': '양자 생물학',
    Genomics: '유전체학',
};

function testIdPart(value) {
    return String(value ?? '')
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '') || 'item';
}

function safeIpfsCid(candidate) {
    const value = String(candidate || '').trim();
    if (!value) return '';
    if (value.length < 32 || value.length > 100) return '';
    if (!/^[A-Za-z0-9]+$/.test(value)) return '';
    return value;
}

function buildIpfsGatewayHref(candidate) {
    const cid = safeIpfsCid(candidate);
    return cid ? `https://ipfs.io/ipfs/${cid}` : '';
}

function buildAmoyTxHref(candidate) {
    const hash = String(candidate || '').trim();
    if (!/^0x[a-fA-F0-9]{64}$/.test(hash)) return '';
    return `https://amoy.polygonscan.com/tx/${hash}`;
}

function buildAnalyzeLoginPath(paper) {
    const params = new URLSearchParams({
        next: '/biolinker',
        intent: 'analyze',
        paper_id: String(paper.id),
    });
    if (paper.title) {
        params.set('paper_title', paper.title);
    }
    return `/login?${params.toString()}`;
}

function normalizePaper(paper, index = 0) {
    const fallback = MOCK_PAPERS[index % MOCK_PAPERS.length] || MOCK_PAPERS[0];
    const source = paper || {};
    const keywords = Array.isArray(source.keywords) ? source.keywords.filter(Boolean) : [];
    const tags = Array.isArray(source.tags) ? source.tags.filter(Boolean) : keywords;
    const field = source.field || tags[0] || fallback.field || 'General Science';
    const cid = source.ipfs_cid || source.cid || fallback.ipfs_cid;
    const cited = Number(source.cited);

    return {
        ...fallback,
        ...source,
        id: source.id || source.cid || fallback.id,
        title: source.title || fallback.title,
        abstract: source.abstract || fallback.abstract,
        authors: Array.isArray(source.authors) ? source.authors.join(', ') : (source.authors || fallback.authors),
        tags: tags.length > 0 ? tags : [field],
        ipfs_cid: cid,
        date: source.date || String(source.created_at || '').slice(0, 10) || fallback.date,
        field,
        cited: Number.isFinite(cited) ? cited : 0,
    };
}

const cardVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: (i) => ({ opacity: 1, y: 0, transition: { delay: i * 0.06, duration: 0.45 } }),
};

export default function ResearchFeed() {
    const { locale } = useLocale();
    const isKo = locale === 'ko-KR';
    useDocumentMeta({
        title: isKo ? '연구 피드 — DecentBio' : 'Research Feed — DecentBio',
        description: isKo
            ? '최신 바이오 연구와 논문을 탐색하고 IPFS에 저장된 연구를 둘러보세요.'
            : 'Explore the latest bio research and papers stored on IPFS.',
        canonicalPath: '/explore',
    });
    const [query, setQuery] = useState('');
    const [activeField, setActiveField] = useState('All');
    const [papersData, setPapersData] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        import('../services/api').then(({ default: api }) => {
            api.get('/papers/public')
                .then((res) => {
                    const papers = Array.isArray(res.data) ? res.data : [];
                    if (papers.length > 0) {
                        setPapersData(papers.map((paper, index) => normalizePaper(paper, index)));
                    } else {
                        setPapersData(MOCK_PAPERS);
                    }
                })
                .catch((err) => {
                    console.error('Failed to fetch public papers:', err);
                    setPapersData(MOCK_PAPERS);
                })
                .finally(() => setLoading(false));
        });
    }, []);

    const papers = useMemo(() => {
        let filtered = papersData.map((paper, index) => normalizePaper(paper, index));
        if (query.trim()) {
            const q = query.toLowerCase();
            filtered = filtered.filter(
                (p) => p.title.toLowerCase().includes(q) ||
                    p.abstract.toLowerCase().includes(q) ||
                    p.tags.some((t) => t.toLowerCase().includes(q))
            );
        }
        if (activeField !== 'All') {
            filtered = filtered.filter((p) => p.field === activeField);
        }
        return filtered;
    }, [query, activeField, papersData]);

    return (
        <div className="relative min-h-screen" style={{ background: 'var(--bg-primary, #f0ece6)' }}>
            <div className="ambient-bg" aria-hidden="true" />

            <nav className="relative z-20 flex items-center justify-between px-6 py-5 lg:px-12">
                <Link to="/" className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-[1.1rem] bg-gradient-to-br from-primary to-accent text-white shadow-clay-soft">
                        <Sparkles className="h-4 w-4" />
                    </div>
                    <span className="font-display text-xl font-semibold text-ink">DSCI</span>
                </Link>
                <div className="flex items-center gap-3">
                    <LocaleToggle />
                    <Link to="/login" className="clay-button clay-button-primary text-sm font-semibold text-white">
                        {isKo ? '시작하기' : 'Get started'}
                        <ArrowRight className="h-4 w-4" />
                    </Link>
                </div>
            </nav>

            <div className="relative z-10 mx-auto max-w-7xl px-6 py-10 lg:px-12">
                <motion.div
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mb-10"
                >
                    <p className="clay-chip mb-3 inline-block">
                        {isKo ? '오픈 사이언스 피드' : 'Open Science Feed'}
                    </p>
                    <h1 className="font-display text-4xl font-semibold text-ink md:text-5xl">
                        {isKo ? 'IPFS에 영구 저장된 연구' : 'Research stored permanently on IPFS'}
                    </h1>
                    <p className="mt-3 max-w-2xl text-base leading-7 text-ink-muted">
                        {isKo
                            ? 'DSCI 플랫폼에 제출된 연구를 탐색하세요. 모든 논문은 IPFS 기반 보존 흐름을 기준으로 정리됩니다.'
                            : 'Browse papers submitted by researchers on the DSCI platform. Every paper is organized around permanent IPFS storage.'}
                    </p>
                </motion.div>

                <div className="mb-8 flex flex-col gap-4 md:flex-row md:items-center">
                    <div className="relative flex-1">
                        <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-soft" />
                        <input
                            type="text"
                            value={query}
                            onChange={(event) => setQuery(event.target.value)}
                            placeholder={isKo ? '제목, 초록, 키워드 검색...' : 'Search title, abstract, keywords...'}
                            className="clay-input w-full pl-11"
                            data-testid="research-feed-search"
                            aria-label={isKo ? '논문 검색' : 'Search papers'}
                        />
                    </div>
                    <div className="flex items-center gap-2 overflow-x-auto pb-1">
                        <Filter className="h-4 w-4 shrink-0 text-ink-soft" />
                        {ALL_FIELDS.map((field) => (
                            <button
                                key={field}
                                type="button"
                                onClick={() => setActiveField(field)}
                                data-testid={`research-feed-field-${testIdPart(field)}`}
                                className={[
                                    'shrink-0 rounded-[1.2rem] px-4 py-2 text-xs font-semibold transition-all',
                                    activeField === field
                                        ? 'bg-gradient-to-r from-primary to-accent text-white shadow-clay-soft'
                                        : 'clay-button text-ink-muted hover:text-ink',
                                ].join(' ')}
                            >
                                {isKo ? FIELD_LABELS_KO[field] : field}
                            </button>
                        ))}
                    </div>
                </div>

                <div className="flex flex-col gap-8 lg:flex-row">
                    <div className="flex-1 space-y-5">
                        <div className="mb-6 flex items-center justify-between">
                            <p className="text-sm text-ink-soft">
                                {isKo ? `${papers.length}개의 논문` : `${papers.length} paper${papers.length !== 1 ? 's' : ''}`}
                                {query && ` - "${query}"`}
                            </p>
                            <div className="flex items-center gap-2 text-xs font-medium text-ink-soft">
                                <span className="flex h-2 w-2 animate-pulse rounded-full bg-emerald-500" />
                                {isKo ? '실시간 동기화 중' : 'Live Syncing'}
                            </div>
                        </div>

                {loading ? (
                    <div className="flex h-48 items-center justify-center">
                        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
                    </div>
                ) : papers.length === 0 ? (
                    <GlassCard className="p-12 text-center">
                        <BookOpen className="mx-auto mb-4 h-12 w-12 text-ink-soft" />
                        <h3 className="font-display text-2xl font-semibold text-ink">
                            {isKo ? '검색 결과가 없습니다' : 'No papers found'}
                        </h3>
                        <p className="mt-2 text-sm text-ink-muted">
                            {isKo ? '다른 키워드나 필터를 시도해 보세요.' : 'Try different keywords or filters.'}
                        </p>
                    </GlassCard>
                ) : (
                    <div className="space-y-5">

                        {papers.map((paper, index) => {
                            const ipfsHref = buildIpfsGatewayHref(paper.ipfs_cid);
                            const txHref = buildAmoyTxHref(paper.tx_hash);
                            return (
                            <motion.div
                                key={paper.id}
                                custom={index}
                                variants={cardVariants}
                                initial="hidden"
                                animate="visible"
                            >
                                <GlassCard className="p-6 transition-all hover:-translate-y-0.5">
                                    <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                                        <div className="min-w-0 flex-1">
                                            <div className="mb-3 flex flex-wrap items-center gap-2">
                                                <Badge variant="default">{isKo ? (FIELD_LABELS_KO[paper.field] || paper.field) : paper.field}</Badge>
                                                <span className="flex items-center gap-1 text-xs text-ink-soft">
                                                    <Clock className="h-3 w-3" />
                                                    {paper.date}
                                                </span>
                                                <span className="flex items-center gap-1 text-xs text-ink-soft">
                                                    <BookOpen className="h-3 w-3" />
                                                    {isKo ? `인용 ${paper.cited}회` : `${paper.cited} citations`}
                                                </span>
                                                {paper.nft_minted && (
                                                    <span className="flex items-center gap-1 text-xs font-semibold text-primary">
                                                        <ShieldCheck className="h-3 w-3" />
                                                        {isKo ? '온체인 증명 완료' : 'On-chain Verified'}
                                                    </span>
                                                )}
                                            </div>
                                            <h2 className="font-display text-xl font-semibold leading-snug text-ink">
                                                {paper.title}
                                            </h2>
                                            <p className="mt-1 flex items-center gap-1.5 text-sm text-ink-muted">
                                                <User className="h-3.5 w-3.5" />
                                                {paper.authors}
                                            </p>
                                            <p className="mt-3 line-clamp-3 text-sm leading-7 text-ink-muted">
                                                {paper.abstract}
                                            </p>
                                            <div className="mt-4 flex flex-wrap gap-2">
                                                {paper.tags.map((tag) => (
                                                    <span
                                                        key={tag}
                                                        className="inline-flex items-center gap-1 rounded-full bg-white/60 px-3 py-1 text-xs font-semibold text-ink shadow-clay-soft"
                                                    >
                                                        <Tag className="h-3 w-3 text-primary" />
                                                        {tag}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>

                                        <div className="flex w-full shrink-0 flex-row flex-wrap gap-2 sm:w-auto md:w-32 md:flex-col">
                                            {ipfsHref ? (
                                                <a
                                                    href={ipfsHref}
                                                    data-testid={`research-feed-ipfs-${paper.id}`}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="clay-button w-full whitespace-nowrap !px-3 text-xs font-semibold text-ink sm:w-auto md:w-full"
                                                    aria-label={isKo ? 'IPFS에서 보기' : 'View on IPFS'}
                                                >
                                                    <Globe className="h-3.5 w-3.5" />
                                                    {isKo ? 'IPFS 보기' : 'IPFS'}
                                                </a>
                                            ) : (
                                                <span
                                                    data-testid={`research-feed-ipfs-unavailable-${paper.id}`}
                                                    className="clay-button w-full cursor-default whitespace-nowrap !px-3 text-xs font-semibold text-ink-soft sm:w-auto md:w-full"
                                                >
                                                    <Globe className="h-3.5 w-3.5" />
                                                    {isKo ? 'IPFS 없음' : 'IPFS unavailable'}
                                                </span>
                                            )}
                                            {txHref ? (
                                                <a
                                                    href={txHref}
                                                    data-testid={`research-feed-tx-${paper.id}`}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="clay-button w-full whitespace-nowrap !px-3 text-xs font-semibold text-ink sm:w-auto md:w-full"
                                                >
                                                    <ExternalLink className="h-3.5 w-3.5" />
                                                    {isKo ? '트랜잭션' : 'Tx'}
                                                </a>
                                            ) : paper.tx_hash ? (
                                                <span
                                                    data-testid={`research-feed-tx-unavailable-${paper.id}`}
                                                    className="clay-button w-full cursor-default whitespace-nowrap !px-3 text-xs font-semibold text-ink-soft sm:w-auto md:w-full"
                                                >
                                                    <ExternalLink className="h-3.5 w-3.5" />
                                                    {isKo ? '트랜잭션 없음' : 'Tx unavailable'}
                                                </span>
                                            ) : (
                                                null
                                            )}
                                            <Link
                                                to={buildAnalyzeLoginPath(paper)}
                                                className="clay-button clay-button-primary w-full whitespace-nowrap !px-3 text-xs font-semibold text-white sm:w-auto md:w-full"
                                                data-testid={`research-feed-analyze-${paper.id}`}
                                            >
                                                <Sparkles className="h-3.5 w-3.5" />
                                                {isKo ? 'AI 분석' : 'Analyze'}
                                            </Link>
                                        </div>
                                    </div>
                                </GlassCard>
                            </motion.div>
                            );
                        })}
                    </div>
                        )}
                    </div>

                    <div className="w-full lg:w-80">
                        <GlassCard className="p-6">
                            <h3 className="mb-4 flex items-center gap-2 font-display text-lg font-semibold text-ink">
                                <Activity className="h-5 w-5 text-primary" />
                                {isKo ? '최근 온체인 활동' : 'Live Activity'}
                            </h3>
                            <div className="space-y-4">
                                {[
                                    { user: '0x3f...a4', action: isKo ? '논문 발행' : 'Minted Paper', time: '2m ago' },
                                    { user: '0x1e...c2', action: isKo ? '보상 수령' : 'Claimed Reward', time: '15m ago' },
                                    { user: '0x9a...b8', action: isKo ? '검토 완료' : 'Peer Reviewed', time: '1h ago' },
                                    { user: '0x7d...e1', action: isKo ? '논문 발행' : 'Minted Paper', time: '3h ago' },
                                ].map((item, i) => (
                                    <div key={i} className="flex items-start justify-between border-b border-white/20 pb-3 last:border-0 last:pb-0">
                                        <div>
                                            <p className="text-xs font-mono text-primary">{item.user}</p>
                                            <p className="text-sm font-medium text-ink">{item.action}</p>
                                        </div>
                                        <span className="text-[10px] text-ink-soft">{item.time}</span>
                                    </div>
                                ))}
                            </div>
                        </GlassCard>

                        <div className="mt-6">
                            <GlassCard className="p-6">
                                <h3 className="mb-2 font-display text-sm font-semibold uppercase tracking-wider text-ink-soft">
                                    {isKo ? '통계' : 'Platform Stats'}
                                </h3>
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <p className="text-2xl font-bold text-ink">1,204</p>
                                        <p className="text-[10px] text-ink-muted">{isKo ? '등록된 논문' : 'Papers indexed'}</p>
                                    </div>
                                    <div>
                                        <p className="text-2xl font-bold text-ink">45.2K</p>
                                        <p className="text-[10px] text-ink-muted">{isKo ? '보상된 DSCI' : 'DSCI Rewarded'}</p>
                                    </div>
                                </div>
                            </GlassCard>
                        </div>
                    </div>
                </div>

                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.5 }}
                    className="mt-12 text-center"
                >
                    <GlassCard className="p-8">
                        <h3 className="font-display text-2xl font-semibold text-ink">
                            {isKo ? '당신의 연구도 여기에 올리세요' : 'Add your research here'}
                        </h3>
                        <p className="mx-auto mt-2 max-w-md text-sm leading-7 text-ink-muted">
                            {isKo
                                ? '논문을 IPFS에 보존하고 AI 매칭, 투자자 노출, DSCI 보상 흐름을 시작하세요.'
                                : 'Store your paper on IPFS and unlock AI matching, investor discovery, and DSCI reward flows.'}
                        </p>
                        <Link to="/login" className="clay-button clay-button-primary mt-6 inline-flex px-8 py-3 text-sm font-semibold text-white">
                            <Sparkles className="h-4 w-4" />
                            {isKo ? '무료로 논문 제출하기' : 'Submit your paper free'}
                            <ArrowRight className="h-4 w-4" />
                        </Link>
                    </GlassCard>
                </motion.div>
            </div>
        </div>
    );
}
