import ReactMarkdown from 'react-markdown';
import { ChevronDown, Copy, Loader2, Microscope, PenTool, RefreshCw, Send, Youtube } from 'lucide-react';
import GlassCard from './ui/GlassCard';
import { Button } from './ui/Button';
import { useAgentTools } from '../hooks/useAgentTools';

export default function AILab() {
    const {
        activeTool, isLoading, result, agentError, agentMeta,
        changeTool, submit, copyResult,
        research, write, youtube, t,
    } = useAgentTools();

    const tools = [
        { id: 'research', label: t('ailab.toolResearch'), icon: Microscope, descriptionKey: 'ailab.researchDescription', placeholder: t('ailab.researchPlaceholder') },
        { id: 'write', label: t('ailab.toolWrite'), icon: PenTool, descriptionKey: 'ailab.writeDescription', placeholder: t('ailab.writePlaceholder') },
        { id: 'youtube', label: t('ailab.toolYoutube'), icon: Youtube, descriptionKey: 'ailab.youtubeDescription', placeholder: t('ailab.youtubePlaceholder') },
    ];

    const formatTypes = [
        { value: 'blog_post', label: t('ailab.formatBlogPost') },
        { value: 'report', label: t('ailab.formatReport') },
        { value: 'summary', label: t('ailab.formatSummary') },
        { value: 'presentation', label: t('ailab.formatPresentation') },
    ];

    const tool = tools.find((item) => item.id === activeTool) ?? tools[0];
    const ToolIcon = tool.icon;

    return (
        <div className="space-y-6">
            <GlassCard className="p-7">
                <p className="clay-chip mb-4">{t('ailab.experiment')}</p>
                <h1 className="font-display text-4xl font-semibold text-ink">{t('ailab.title')}</h1>
                <p className="mt-3 text-sm leading-7 text-ink-muted">{t('ailab.subtitle')}</p>
            </GlassCard>

            <div className="clay-panel-pressed inline-flex rounded-full p-1">
                {tools.map((item) => {
                    const Icon = item.icon;
                    const active = activeTool === item.id;
                    return (
                        <button
                            key={item.id}
                            type="button"
                            onClick={() => changeTool(item.id)}
                            className={[
                                'inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold transition-all',
                                active ? 'bg-white text-ink shadow-clay-soft' : 'text-ink-soft hover:text-ink',
                            ].join(' ')}
                        >
                            <Icon className="h-4 w-4" />
                            {item.label}
                        </button>
                    );
                })}
            </div>

            <GlassCard className="p-6">
                <p className="mb-4 text-sm leading-7 text-ink-muted">{t(tool.descriptionKey)}</p>

                {activeTool === 'research' && (
                    <div className="space-y-3">
                        <input
                            className="clay-input w-full"
                            placeholder={tool.placeholder}
                            value={research.researchTopic}
                            onChange={(event) => research.setResearchTopic(event.target.value)}
                            onKeyDown={(event) => event.key === 'Enter' && submit()}
                        />
                        <label className="inline-flex items-center gap-2 text-sm text-ink-muted">
                            <input type="checkbox" checked={research.deepMode} onChange={(event) => research.setDeepMode(event.target.checked)} />
                            {t('ailab.deepResearchMode')}
                        </label>
                    </div>
                )}

                {activeTool === 'write' && (
                    <div className="space-y-3">
                        <div className="grid gap-3 md:grid-cols-[1fr,220px]">
                            <input className="clay-input w-full" placeholder={t('ailab.writeTopicPlaceholder')} value={write.writeTopic} onChange={(event) => write.setWriteTopic(event.target.value)} />
                            <div className="relative">
                                <select value={write.formatType} onChange={(event) => write.setFormatType(event.target.value)} className="clay-input appearance-none pr-10">
                                    {formatTypes.map((format) => (
                                        <option key={format.value} value={format.value}>{format.label}</option>
                                    ))}
                                </select>
                                <ChevronDown className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-soft" />
                            </div>
                        </div>
                        <textarea className="clay-input min-h-[220px] resize-none" placeholder={t('ailab.writePlaceholder')} value={write.writeRawText} onChange={(event) => write.setWriteRawText(event.target.value)} />
                    </div>
                )}

                {activeTool === 'youtube' && (
                    <div className="space-y-3">
                        <input className="clay-input w-full" placeholder={tool.placeholder} value={youtube.youtubeUrl} onChange={(event) => youtube.setYoutubeUrl(event.target.value)} />
                        <input className="clay-input w-full" placeholder={t('ailab.youtubeQuestionPlaceholder')} value={youtube.youtubeQuery} onChange={(event) => youtube.setYoutubeQuery(event.target.value)} onKeyDown={(event) => event.key === 'Enter' && submit()} />
                    </div>
                )}

                <Button onClick={submit} disabled={isLoading} className="mt-4 justify-center text-white">
                    {isLoading ? <><Loader2 className="h-4 w-4 animate-spin" />{t('common.processing')}</> : <><Send className="h-4 w-4" />{t('ailab.submit')}</>}
                </Button>
            </GlassCard>

            {isLoading && !result && (
                <GlassCard className="p-10 text-center">
                    <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-4 border-white/70 border-t-primary" />
                    <h3 className="font-display text-2xl font-semibold text-ink">{t('ailab.loadingTitle')}</h3>
                    <p className="mt-3 text-sm text-ink-muted">{t('ailab.loadingBody')}</p>
                </GlassCard>
            )}

            {agentError && !isLoading && (
                <GlassCard className="p-6">
                    <p className="mb-2 text-sm font-semibold text-error-dark">{t('ailab.failedTitle')}</p>
                    <p className="text-sm text-ink-muted">{agentError}</p>
                    <Button onClick={submit} className="mt-4 justify-center text-white">
                        <RefreshCw className="h-4 w-4" />
                        {t('common.retry')}
                    </Button>
                </GlassCard>
            )}

            {result && (
                <GlassCard className="p-0 overflow-hidden">
                    <div className="flex items-center justify-between border-b border-white/60 px-6 py-4">
                        <div className="flex items-center gap-3">
                            <span className="flex h-10 w-10 items-center justify-center rounded-full bg-white text-primary shadow-clay-soft">
                                <ToolIcon className="h-4 w-4" />
                            </span>
                            <div>
                                <p className="text-sm font-semibold text-ink">{t('ailab.resultTitle')}</p>
                                {agentMeta?.bridge_applied && <p className="text-xs uppercase tracking-[0.18em] text-primary">{t('common.bridgeApplied')}</p>}
                            </div>
                        </div>
                        <button onClick={copyResult} className="clay-button">
                            <Copy className="h-4 w-4" />
                            {t('common.copy')}
                        </button>
                    </div>
                    <div className="p-6 prose max-w-none prose-headings:font-display prose-headings:text-ink prose-p:text-ink-muted prose-a:text-primary prose-strong:text-ink">
                        <ReactMarkdown>{result}</ReactMarkdown>
                    </div>
                </GlassCard>
            )}
        </div>
    );
}
