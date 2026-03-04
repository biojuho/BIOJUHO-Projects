import ReactMarkdown from 'react-markdown';
import GlassCard from './ui/GlassCard';
import { useAgentTools } from '../hooks/useAgentTools';
import {
    Microscope, PenTool, Youtube, Send, Loader2, Copy, ChevronDown, RefreshCw,
} from 'lucide-react';

const TOOLS = [
    {
        id: 'research',
        label: 'Deep Research',
        icon: Microscope,
        color: 'primary',
        descriptionKey: 'ailab.researchDescription',
        placeholder: '예: Agentic AI in Drug Discovery',
    },
    {
        id: 'write',
        label: 'Content Writer',
        icon: PenTool,
        color: 'accent',
        descriptionKey: 'ailab.writeDescription',
        placeholder: '예: CRISPR 유전자 편집 기술 동향',
    },
    {
        id: 'youtube',
        label: 'YouTube Intelligence',
        icon: Youtube,
        color: 'highlight',
        descriptionKey: 'ailab.youtubeDescription',
        placeholder: 'YouTube URL 입력',
    },
];

const FORMAT_TYPES = [
    { value: 'blog_post', label: 'Blog Post' },
    { value: 'report', label: 'Research Report' },
    { value: 'summary', label: 'Executive Summary' },
    { value: 'presentation', label: 'Presentation Script' },
];

const COLOR_MAP = {
    primary: { bg: 'bg-primary/10', text: 'text-primary', border: 'border-primary/20', activeBg: 'bg-primary/15' },
    accent: { bg: 'bg-accent/10', text: 'text-accent-light', border: 'border-accent/20', activeBg: 'bg-accent/15' },
    highlight: { bg: 'bg-highlight/10', text: 'text-highlight', border: 'border-highlight/20', activeBg: 'bg-highlight/15' },
};

export default function AILab() {
    const {
        activeTool, isLoading, result, agentError, agentMeta,
        changeTool, submit, copyResult,
        research, write, youtube, t,
    } = useAgentTools();

    const tool = TOOLS.find((item) => item.id === activeTool) ?? TOOLS[0];
    const colors = COLOR_MAP[tool.color];
    const ToolIcon = tool.icon;

    return (
        <div className="space-y-6">
            <div>
                <p className="text-xs text-white/30 uppercase tracking-[0.2em] font-medium mb-2">{t('ailab.experiment')}</p>
                <h1 className="font-display text-3xl font-bold text-white tracking-tight">
                    AI Research <span className="text-gradient">Lab</span>
                </h1>
                <p className="text-white/30 text-sm mt-1">{t('ailab.subtitle')}</p>
            </div>

            <div className="flex bg-white/[0.03] p-1 rounded-xl border border-white/[0.06] w-fit">
                {TOOLS.map((item) => {
                    const Icon = item.icon;
                    const isActive = activeTool === item.id;
                    const tc = COLOR_MAP[item.color];
                    return (
                        <button
                            key={item.id}
                            onClick={() => changeTool(item.id)}
                            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-300 ${
                                isActive
                                    ? `${tc.activeBg} ${tc.text} border ${tc.border}`
                                    : 'text-white/35 hover:text-white/60 border border-transparent'
                            }`}
                        >
                            <Icon className="w-4 h-4" />
                            {item.label}
                        </button>
                    );
                })}
            </div>

            <GlassCard className="p-6">
                <p className="text-white/40 text-sm mb-4">{t(tool.descriptionKey)}</p>

                {activeTool === 'research' && (
                    <div className="space-y-3">
                        <input
                            className="glass-input w-full"
                            placeholder={tool.placeholder}
                            value={research.researchTopic}
                            onChange={(event) => research.setResearchTopic(event.target.value)}
                            onKeyDown={(event) => event.key === 'Enter' && submit()}
                        />
                        <label className="flex items-center gap-2 text-sm text-white/50 cursor-pointer select-none">
                            <input
                                type="checkbox"
                                checked={research.deepMode}
                                onChange={(event) => research.setDeepMode(event.target.checked)}
                                className="rounded border-white/20 bg-white/[0.04] text-primary focus:ring-primary/30"
                            />
                            {t('ailab.deepResearchMode')}
                        </label>
                    </div>
                )}

                {activeTool === 'write' && (
                    <div className="space-y-3">
                        <div className="flex gap-3">
                            <input
                                className="glass-input flex-1"
                                placeholder={t('ailab.writeTopicPlaceholder')}
                                value={write.writeTopic}
                                onChange={(event) => write.setWriteTopic(event.target.value)}
                            />
                            <div className="relative">
                                <select
                                    value={write.formatType}
                                    onChange={(event) => write.setFormatType(event.target.value)}
                                    className="glass-input appearance-none cursor-pointer pr-8 min-w-[160px]"
                                >
                                    {FORMAT_TYPES.map((format) => (
                                        <option key={format.value} value={format.value}>{format.label}</option>
                                    ))}
                                </select>
                                <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/25 pointer-events-none" />
                            </div>
                        </div>
                        <textarea
                            className="glass-input w-full h-32 resize-none"
                            placeholder={t('ailab.writePlaceholder')}
                            value={write.writeRawText}
                            onChange={(event) => write.setWriteRawText(event.target.value)}
                        />
                    </div>
                )}

                {activeTool === 'youtube' && (
                    <div className="space-y-3">
                        <input
                            className="glass-input w-full"
                            placeholder="https://youtube.com/watch?v=..."
                            value={youtube.youtubeUrl}
                            onChange={(event) => youtube.setYoutubeUrl(event.target.value)}
                        />
                        <input
                            className="glass-input w-full"
                            placeholder={t('ailab.youtubeQuestionPlaceholder')}
                            value={youtube.youtubeQuery}
                            onChange={(event) => youtube.setYoutubeQuery(event.target.value)}
                            onKeyDown={(event) => event.key === 'Enter' && submit()}
                        />
                    </div>
                )}

                <button
                    onClick={submit}
                    disabled={isLoading}
                    className="glass-button mt-4 px-6 py-2.5 font-semibold flex items-center gap-2 disabled:opacity-40"
                >
                    {isLoading ? (
                        <><Loader2 className="w-4 h-4 animate-spin" /> {t('common.processing')}</>
                    ) : (
                        <><Send className="w-4 h-4" /> {t('ailab.submit')}</>
                    )}
                </button>
            </GlassCard>

            {isLoading && !result && (
                <GlassCard className="p-10 text-center">
                    <div className="inline-block animate-spin rounded-full h-10 w-10 border-2 border-white/10 border-t-primary mb-4"></div>
                    <h3 className="font-display text-base font-semibold text-white">{t('ailab.loadingTitle')}</h3>
                    <p className="text-white/25 mt-2 text-sm">{t('ailab.loadingBody')}</p>
                </GlassCard>
            )}

            {agentError && !isLoading && (
                <GlassCard className="p-6 border-red-500/20 bg-red-500/[0.04]">
                    <div className="flex items-start justify-between gap-4">
                        <div>
                            <p className="text-sm font-semibold text-red-400 mb-1">{t('ailab.failedTitle')}</p>
                            <p className="text-white/40 text-xs">{agentError}</p>
                        </div>
                        <button
                            onClick={submit}
                            className="glass-button px-4 py-2 text-sm font-semibold flex items-center gap-2 shrink-0"
                        >
                            <RefreshCw className="w-4 h-4" /> {t('common.retry')}
                        </button>
                    </div>
                </GlassCard>
            )}

            {result && (
                <GlassCard className="p-0 overflow-hidden">
                    <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
                        <div className="flex items-center gap-3">
                            <h3 className="font-display text-base font-semibold text-white flex items-center gap-2">
                                <span className={`p-1.5 rounded-lg ${colors.bg}`}>
                                    <ToolIcon className={`w-4 h-4 ${colors.text}`} />
                                </span>
                                {t('ailab.resultTitle')}
                            </h3>
                            {agentMeta?.bridge_applied && (
                                <span className="text-[10px] uppercase tracking-[0.2em] px-2.5 py-1 rounded-full border border-primary/25 text-primary bg-primary/10">
                                    {t('common.bridgeApplied')}
                                </span>
                            )}
                        </div>
                        <button
                            onClick={copyResult}
                            className="text-xs text-white/30 hover:text-white/60 flex items-center gap-1.5 transition-colors"
                        >
                            <Copy className="w-3.5 h-3.5" /> {t('common.copy')}
                        </button>
                    </div>
                    <div className="p-6 prose prose-invert max-w-none prose-headings:font-display prose-headings:text-white prose-p:text-white/70 prose-a:text-primary prose-strong:text-white">
                        <ReactMarkdown>{result}</ReactMarkdown>
                    </div>
                </GlassCard>
            )}
        </div>
    );
}
