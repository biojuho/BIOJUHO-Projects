/**
 * Notices Browser Page
 * Browse and filter KDDF/NTIS government grant notices
 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Search,
    Filter,
    ExternalLink,
    Calendar,
    Building2,
    RefreshCw,
    FileText,
    ChevronDown,
} from 'lucide-react';
import client from '../services/api';
import { useToast } from '../contexts/ToastContext';
import { useLocale } from '../contexts/LocaleContext';
import GlassCard from './ui/GlassCard';
import { SkeletonList } from './ui/Skeleton';

export default function Notices() {
    const { showToast } = useToast();
    const { t } = useLocale();
    const navigate = useNavigate();
    const [notices, setNotices] = useState([]);
    const [loading, setLoading] = useState(true);
    const [collecting, setCollecting] = useState(false);
    const [sourceFilter, setSourceFilter] = useState('');
    const [searchTerm, setSearchTerm] = useState('');
    const [limit, setLimit] = useState(30);

    const fetchNotices = async () => {
        setLoading(true);
        try {
            const params = { limit };
            if (sourceFilter) {
                params.source = sourceFilter;
            }
            const response = await client.get('/notices', { params });
            setNotices(Array.isArray(response.data) ? response.data : []);
        } catch (err) {
            console.error('Failed to fetch notices:', err);
            showToast({ key: 'notices.fetchFailed' }, 'error');
        } finally {
            setLoading(false);
        }
    };

    const handleCollect = async () => {
        setCollecting(true);
        try {
            const response = await client.post('/notices/collect');
            showToast({
                key: 'notices.collectSuccess',
                values: { count: response.data.collected },
            }, 'success');
            fetchNotices();
        } catch (err) {
            showToast({
                key: 'notices.collectFailed',
                values: { message: err.response?.data?.detail || err.message },
            }, 'error');
        } finally {
            setCollecting(false);
        }
    };

    useEffect(() => {
        fetchNotices();
    }, [sourceFilter, limit]); // eslint-disable-line react-hooks/exhaustive-deps

    const filtered = notices.filter((notice) => {
        if (!searchTerm) {
            return true;
        }
        const term = searchTerm.toLowerCase();
        const title = (notice.title || notice.metadata?.title || '').toLowerCase();
        const body = (notice.body_text || notice.metadata?.body_text || '').toLowerCase();
        const source = (notice.source || notice.metadata?.source || '').toLowerCase();
        return title.includes(term) || body.includes(term) || source.includes(term);
    });

    return (
        <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
                <div>
                    <p className="text-xs text-white/30 uppercase tracking-[0.2em] font-medium mb-2">{t('notices.browse')}</p>
                    <h1 className="font-display text-3xl font-bold text-white tracking-tight">
                        {t('notices.titlePrefix')} <span className="text-gradient">{t('notices.titleHighlight')}</span>
                    </h1>
                    <p className="text-white/30 text-sm mt-1">{t('notices.subtitle')}</p>
                </div>
                <button
                    onClick={handleCollect}
                    disabled={collecting}
                    className="glass-button px-5 py-2.5 font-semibold flex items-center gap-2 disabled:opacity-40"
                >
                    <RefreshCw className={`w-4 h-4 ${collecting ? 'animate-spin' : ''}`} />
                    {collecting ? t('notices.collecting') : t('notices.collectLatest')}
                </button>
            </div>

            <GlassCard className="p-5">
                <div className="flex flex-col sm:flex-row gap-3">
                    <div className="relative flex-1">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/25" />
                        <input
                            type="text"
                            placeholder={t('notices.searchPlaceholder')}
                            value={searchTerm}
                            onChange={(event) => setSearchTerm(event.target.value)}
                            className="glass-input w-full pl-10"
                        />
                    </div>
                    <div className="relative">
                        <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/25" />
                        <select
                            value={sourceFilter}
                            onChange={(event) => setSourceFilter(event.target.value)}
                            className="glass-input pl-10 pr-8 appearance-none cursor-pointer min-w-[140px]"
                        >
                            <option value="">{t('notices.allSources')}</option>
                            <option value="KDDF">KDDF</option>
                            <option value="NTIS">NTIS</option>
                        </select>
                        <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/25 pointer-events-none" />
                    </div>
                    <select
                        value={limit}
                        onChange={(event) => setLimit(Number(event.target.value))}
                        className="glass-input appearance-none cursor-pointer w-[100px]"
                    >
                        <option value={15}>15건</option>
                        <option value={30}>30건</option>
                        <option value={50}>50건</option>
                        <option value={100}>100건</option>
                    </select>
                </div>
            </GlassCard>

            <div className="flex items-center gap-4 text-sm text-white/30">
                <span className="flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5" />
                    {t('notices.displayedCount', { count: filtered.length })}
                </span>
                {sourceFilter && (
                    <span className="badge-primary text-xs px-2 py-0.5 rounded-md">
                        {sourceFilter}
                    </span>
                )}
            </div>

            {loading ? (
                <SkeletonList count={5} className="pt-2" />
            ) : filtered.length === 0 ? (
                <GlassCard className="p-12 text-center">
                    <FileText className="w-12 h-12 text-white/10 mx-auto mb-4" />
                    <h3 className="font-display text-lg font-semibold text-white/60 mb-2">{t('notices.emptyTitle')}</h3>
                    <p className="text-white/25 text-sm">{t('notices.emptyDescription')}</p>
                </GlassCard>
            ) : (
                <div className="space-y-3">
                    {filtered.map((notice, index) => {
                        const title = notice.title || notice.metadata?.title || t('notices.untitled');
                        const source = notice.source || notice.metadata?.source || '';
                        const budget = notice.budget_range || notice.metadata?.budget_range || '';
                        const deadline = notice.deadline || notice.metadata?.deadline || '';
                        const url = notice.url || notice.metadata?.url || '';
                        const keywords = notice.keywords || notice.metadata?.keywords || [];

                        return (
                            <GlassCard
                                key={notice.id || index}
                                className="p-5 hover:border-primary/20 transition-all duration-300 group"
                                hoverEffect
                            >
                                <div className="flex flex-col lg:flex-row lg:items-start gap-4">
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-2">
                                            {source && (
                                                <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md ${
                                                    source === 'KDDF'
                                                        ? 'bg-primary/10 text-primary border border-primary/20'
                                                        : 'bg-accent/10 text-accent-light border border-accent/20'
                                                }`}>
                                                    {source}
                                                </span>
                                            )}
                                            {budget && (
                                                <span className="text-[11px] text-highlight/70 flex items-center gap-1">
                                                    <Building2 className="w-3 h-3" /> {budget}
                                                </span>
                                            )}
                                        </div>
                                        <h3 className="font-display text-base font-semibold text-white group-hover:text-primary transition-colors line-clamp-2 mb-2">
                                            {title}
                                        </h3>
                                        <div className="flex flex-wrap items-center gap-3 text-xs text-white/25">
                                            {deadline && (
                                                <span className="flex items-center gap-1">
                                                    <Calendar className="w-3 h-3" /> {t('notices.deadline')}: {deadline}
                                                </span>
                                            )}
                                            {keywords.length > 0 && (
                                                <div className="flex gap-1.5 flex-wrap">
                                                    {keywords.slice(0, 4).map((keyword, keywordIndex) => (
                                                        <span key={keywordIndex} className="bg-white/[0.04] px-2 py-0.5 rounded text-white/40">
                                                            {keyword}
                                                        </span>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2 shrink-0">
                                        {url && (
                                            <a
                                                href={url}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="glass-button px-3 py-2 text-xs flex items-center gap-1.5"
                                            >
                                                <ExternalLink className="w-3.5 h-3.5" /> {t('notices.viewOriginal')}
                                            </a>
                                        )}
                                        <button
                                            onClick={() => navigate('/biolinker', {
                                                state: {
                                                    rfp_text: notice.body_text || notice.description || '',
                                                    rfp_title: notice.title || '',
                                                    from_notice: true,
                                                },
                                            })}
                                            className="px-3 py-2 text-xs font-semibold bg-primary/10 text-primary border border-primary/20 rounded-xl hover:bg-primary/20 transition-colors flex items-center gap-1.5"
                                        >
                                            <Search className="w-3.5 h-3.5" /> {t('notices.analyzeFit')}
                                        </button>
                                    </div>
                                </div>
                            </GlassCard>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

