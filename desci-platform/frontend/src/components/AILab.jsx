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
        description: '주제에 대한 심층 연구 리포트를 AI가 생성합니다.',
        placeholder: '예: Agentic AI in Drug Discovery',
    },
    {
        id: 'write',
        label: 'Content Writer',
        icon: PenTool,
        color: 'accent',
        description: '연구 내용을 다양한 형식(블로그, 보고서 등)으로 변환합니다.',
        placeholder: '예: CRISPR 유전자 편집 기술 동향',
    },
    {
        id: 'youtube',
        label: 'YouTube Intelligence',
        icon: Youtube,
        color: 'highlight',
        description: 'YouTube 영상을 분석하고 핵심 내용을 요약합니다.',
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
        activeTool, isLoading, result, agentError,
        changeTool, submit, copyResult,
        research, write, youtube,
    } = useAgentTools();

    const tool = TOOLS.find(t => t.id === activeTool) ?? TOOLS[0];
    const colors = COLOR_MAP[tool.color];

    return (
        <div className="space-y-6">
            {/* Header */}
            <div>
                <p className="text-xs text-white/30 uppercase tracking-[0.2em] font-medium mb-2">Experiment</p>
                <h1 className="font-display text-3xl font-bold text-white tracking-tight">
                    AI Research <span className="text-gradient">Lab</span>
                </h1>
                <p className="text-white/30 text-sm mt-1">Deep Research, Content Writing, Video Intelligence</p>
            </div>

            {/* Tool Selector */}
            <div className="flex bg-white/[0.03] p-1 rounded-xl border border-white/[0.06] w-fit">
                {TOOLS.map(t => {
                    const Icon = t.icon;
                    const isActive = activeTool === t.id;
                    const tc = COLOR_MAP[t.color];
                    return (
                        <button
                            key={t.id}
                            onClick={() => changeTool(t.id)}
                            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-300 ${
                                isActive
                                    ? `${tc.activeBg} ${tc.text} border ${tc.border}`
                                    : 'text-white/35 hover:text-white/60 border border-transparent'
                            }`}
                        >
                            <Icon className="w-4 h-4" />
                            {t.label}
                        </button>
                    );
                })}
            </div>

            {/* Tool Input */}
            <GlassCard className="p-6">
                <p className="text-white/40 text-sm mb-4">{tool.description}</p>

                {activeTool === 'research' && (
                    <div className="space-y-3">
                        <input
                            className="glass-input w-full"
                            placeholder={tool.placeholder}
                            value={research.researchTopic}
                            onChange={e => research.setResearchTopic(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && submit()}
                        />
                        <label className="flex items-center gap-2 text-sm text-white/50 cursor-pointer select-none">
                            <input
                                type="checkbox"
                                checked={research.deepMode}
                                onChange={e => research.setDeepMode(e.target.checked)}
                                className="rounded border-white/20 bg-white/[0.04] text-primary focus:ring-primary/30"
                            />
                            Deep Research Mode (더 심층적인 분석, 시간 더 소요)
                        </label>
                    </div>
                )}

                {activeTool === 'write' && (
                    <div className="space-y-3">
                        <div className="flex gap-3">
                            <input
                                className="glass-input flex-1"
                                placeholder="주제"
                                value={write.writeTopic}
                                onChange={e => write.setWriteTopic(e.target.value)}
                            />
                            <div className="relative">
                                <select
                                    value={write.formatType}
                                    onChange={e => write.setFormatType(e.target.value)}
                                    className="glass-input appearance-none cursor-pointer pr-8 min-w-[160px]"
                                >
                                    {FORMAT_TYPES.map(f => (
                                        <option key={f.value} value={f.value}>{f.label}</option>
                                    ))}
                                </select>
                                <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/25 pointer-events-none" />
                            </div>
                        </div>
                        <textarea
                            className="glass-input w-full h-32 resize-none"
                            placeholder="원본 연구 텍스트를 붙여넣으세요..."
                            value={write.writeRawText}
                            onChange={e => write.setWriteRawText(e.target.value)}
                        />
                    </div>
                )}

                {activeTool === 'youtube' && (
                    <div className="space-y-3">
                        <input
                            className="glass-input w-full"
                            placeholder="https://youtube.com/watch?v=..."
                            value={youtube.youtubeUrl}
                            onChange={e => youtube.setYoutubeUrl(e.target.value)}
                        />
                        <input
                            className="glass-input w-full"
                            placeholder="질문 (선택) 예: 핵심 기술을 요약해줘"
                            value={youtube.youtubeQuery}
                            onChange={e => youtube.setYoutubeQuery(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && submit()}
                        />
                    </div>
                )}

                <button
                    onClick={submit}
                    disabled={isLoading}
                    className="glass-button mt-4 px-6 py-2.5 font-semibold flex items-center gap-2 disabled:opacity-40"
                >
                    {isLoading ? (
                        <><Loader2 className="w-4 h-4 animate-spin" /> 처리 중...</>
                    ) : (
                        <><Send className="w-4 h-4" /> 실행</>
                    )}
                </button>
            </GlassCard>

            {/* Loading */}
            {isLoading && !result && (
                <GlassCard className="p-10 text-center">
                    <div className="inline-block animate-spin rounded-full h-10 w-10 border-2 border-white/10 border-t-primary mb-4"></div>
                    <h3 className="font-display text-base font-semibold text-white">AI 에이전트가 작업 중입니다...</h3>
                    <p className="text-white/25 mt-2 text-sm">데이터 수집 및 분석에 10~60초 정도 소요될 수 있습니다.</p>
                </GlassCard>
            )}

            {/* Error + Retry */}
            {agentError && !isLoading && (
                <GlassCard className="p-6 border-red-500/20 bg-red-500/[0.04]">
                    <div className="flex items-start justify-between gap-4">
                        <div>
                            <p className="text-sm font-semibold text-red-400 mb-1">에이전트 실행 실패</p>
                            <p className="text-white/40 text-xs">{agentError}</p>
                        </div>
                        <button
                            onClick={submit}
                            className="glass-button px-4 py-2 text-sm font-semibold flex items-center gap-2 shrink-0"
                        >
                            <RefreshCw className="w-4 h-4" /> 재시도
                        </button>
                    </div>
                </GlassCard>
            )}

            {/* Result */}
            {result && (
                <GlassCard className="p-0 overflow-hidden">
                    <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
                        <h3 className="font-display text-base font-semibold text-white flex items-center gap-2">
                            <span className={`p-1.5 rounded-lg ${colors.bg}`}>
                                <tool.icon className={`w-4 h-4 ${colors.text}`} />
                            </span>
                            Result
                        </h3>
                        <button
                            onClick={copyResult}
                            className="text-xs text-white/30 hover:text-white/60 flex items-center gap-1.5 transition-colors"
                        >
                            <Copy className="w-3.5 h-3.5" /> 복사
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
