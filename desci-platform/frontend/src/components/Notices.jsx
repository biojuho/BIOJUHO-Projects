import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Calendar, ExternalLink, RefreshCw, Search } from 'lucide-react';
import client from '../services/api';
import { useToast } from '../contexts/ToastContext';
import { useLocale } from '../contexts/LocaleContext';
import GlassCard from './ui/GlassCard';
import { Button } from './ui/Button';
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
            if (sourceFilter) params.source = sourceFilter;
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
            showToast({ key: 'notices.collectSuccess', values: { count: response.data.collected } }, 'success');
            fetchNotices();
        } catch (err) {
            showToast({ key: 'notices.collectFailed', values: { message: err.response?.data?.detail || err.message } }, 'error');
        } finally {
            setCollecting(false);
        }
    };

    useEffect(() => {
        fetchNotices();
    }, [sourceFilter, limit]); // eslint-disable-line react-hooks/exhaustive-deps

    const filtered = notices.filter((notice) => {
        if (!searchTerm) return true;
        const term = searchTerm.toLowerCase();
        const title = (notice.title || notice.metadata?.title || '').toLowerCase();
        const body = (notice.body_text || notice.metadata?.body_text || '').toLowerCase();
        const source = (notice.source || notice.metadata?.source || '').toLowerCase();
        return title.includes(term) || body.includes(term) || source.includes(term);
    });

    return (
        <div className="space-y-6">
            <GlassCard className="p-7">
                <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
                    <div>
                        <p className="clay-chip mb-4">{t('notices.browse')}</p>
                        <h1 className="font-display text-4xl font-semibold text-ink">
                            {t('notices.titlePrefix')} <span className="text-gradient">{t('notices.titleHighlight')}</span>
                        </h1>
                        <p className="mt-3 max-w-3xl text-sm leading-7 text-ink-muted">{t('notices.subtitle')}</p>
                    </div>
                    <Button onClick={handleCollect} disabled={collecting} className="justify-center text-white">
                        <RefreshCw className={`h-4 w-4 ${collecting ? 'animate-spin' : ''}`} />
                        {collecting ? t('notices.collecting') : t('notices.collectLatest')}
                    </Button>
                </div>
            </GlassCard>

            <GlassCard className="p-5">
                <div className="grid gap-3 lg:grid-cols-[1fr,180px,140px]">
                    <div className="relative">
                        <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-soft" />
                        <input
                            type="text"
                            placeholder={t('notices.searchPlaceholder')}
                            value={searchTerm}
                            onChange={(event) => setSearchTerm(event.target.value)}
                            className="clay-input pl-11"
                        />
                    </div>
                    <select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value)} className="clay-input">
                        <option value="">{t('notices.allSources')}</option>
                        <option value="KDDF">KDDF</option>
                        <option value="NTIS">NTIS</option>
                    </select>
                    <select value={limit} onChange={(event) => setLimit(Number(event.target.value))} className="clay-input">
                        <option value={15}>{t('notices.perPage15')}</option>
                        <option value={30}>{t('notices.perPage30')}</option>
                        <option value={50}>{t('notices.perPage50')}</option>
                        <option value={100}>{t('notices.perPage100')}</option>
                    </select>
                </div>
            </GlassCard>

            <p className="text-sm text-ink-muted">{t('notices.displayedCount', { count: filtered.length })}</p>

            {loading ? (
                <SkeletonList count={5} />
            ) : filtered.length === 0 ? (
                <GlassCard className="p-10 text-center">
                    <p className="font-semibold text-ink">{t('notices.emptyTitle')}</p>
                    <p className="mt-2 text-sm text-ink-muted">{t('notices.emptyDescription')}</p>
                </GlassCard>
            ) : (
                <div className="space-y-4">
                    {filtered.map((notice, index) => {
                        const title = notice.title || notice.metadata?.title || t('notices.untitled');
                        const source = notice.source || notice.metadata?.source || '';
                        const budget = notice.budget_range || notice.metadata?.budget_range || '';
                        const deadline = notice.deadline || notice.metadata?.deadline || '';
                        const url = notice.url || notice.metadata?.url || '';
                        const keywords = notice.keywords || notice.metadata?.keywords || [];

                        return (
                            <GlassCard key={notice.id || index} className="p-6" hoverEffect>
                                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                                    <div className="min-w-0 flex-1">
                                        <div className="mb-3 flex flex-wrap items-center gap-2">
                                            {source && <span className="rounded-full bg-primary/15 px-3 py-1 text-xs font-bold uppercase tracking-[0.16em] text-primary">{source}</span>}
                                            {budget && <span className="rounded-full bg-white/70 px-3 py-1 text-xs font-semibold text-ink-muted">{budget}</span>}
                                        </div>
                                        <h3 className="font-display text-2xl font-semibold text-ink">{title}</h3>
                                        <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-ink-muted">
                                            {deadline && (
                                                <span className="inline-flex items-center gap-2">
                                                    <Calendar className="h-4 w-4" />
                                                    {t('notices.deadline')}: {deadline}
                                                </span>
                                            )}
                                        </div>
                                        {keywords.length > 0 && (
                                            <div className="mt-4 flex flex-wrap gap-2">
                                                {keywords.slice(0, 4).map((keyword, keywordIndex) => (
                                                    <span key={keywordIndex} className="rounded-full bg-white/65 px-3 py-1 text-xs font-semibold text-ink-muted">
                                                        {keyword}
                                                    </span>
                                                ))}
                                            </div>
                                        )}
                                    </div>

                                    <div className="flex gap-2">
                                        {url && (
                                            <a href={url} target="_blank" rel="noopener noreferrer" className="clay-button">
                                                <ExternalLink className="h-4 w-4" />
                                                {t('notices.viewOriginal')}
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
                                            className="clay-button clay-button-primary text-white"
                                        >
                                            <Search className="h-4 w-4" />
                                            {t('notices.analyzeFit')}
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
