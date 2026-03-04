import { useState } from 'react';
import client from '../services/api';
import { useToast } from '../contexts/ToastContext';
import { useLocale } from '../contexts/LocaleContext';

/**
 * @typedef {'research' | 'write' | 'youtube'} ToolId
 */

export function useAgentTools() {
    const { showToast } = useToast();
    const { t } = useLocale();

    const [activeTool, setActiveTool] = useState(/** @type {ToolId} */ ('research'));
    const [isLoading, setIsLoading] = useState(false);
    const [result, setResult] = useState('');
    const [agentError, setAgentError] = useState(/** @type {string | null} */ (null));
    const [agentMeta, setAgentMeta] = useState(null);

    const [researchTopic, setResearchTopic] = useState('');
    const [deepMode, setDeepMode] = useState(true);

    const [writeTopic, setWriteTopic] = useState('');
    const [writeRawText, setWriteRawText] = useState('');
    const [formatType, setFormatType] = useState('blog_post');

    const [youtubeUrl, setYoutubeUrl] = useState('');
    const [youtubeQuery, setYoutubeQuery] = useState('');

    const beginRequest = () => {
        setIsLoading(true);
        setResult('');
        setAgentError(null);
        setAgentMeta(null);
    };

    const handleResearch = async () => {
        if (!researchTopic.trim()) {
            showToast({ key: 'agent.researchTopicRequired' }, 'warning');
            return;
        }
        beginRequest();
        try {
            const res = await client.post('/api/agent/research', { topic: researchTopic, deep: deepMode });
            setResult(res.data.result?.report || res.data.report || JSON.stringify(res.data, null, 2));
            setAgentMeta(res.data.meta || res.data.result?.meta || null);
            showToast({ key: 'agent.researchComplete' }, 'success');
        } catch (err) {
            const msg = err.response?.data?.detail || err.message;
            setAgentError(msg);
            showToast({ key: 'agent.researchFailed', values: { message: msg } }, 'error');
        } finally {
            setIsLoading(false);
        }
    };

    const handleWrite = async () => {
        if (!writeTopic.trim() || !writeRawText.trim()) {
            showToast({ key: 'agent.writeInputRequired' }, 'warning');
            return;
        }
        beginRequest();
        try {
            const res = await client.post('/api/agent/write', {
                topic: writeTopic,
                raw_text: writeRawText,
                format_type: formatType,
            });
            setResult(res.data.content || '');
            setAgentMeta(res.data.meta || null);
            showToast({ key: 'agent.writeComplete' }, 'success');
        } catch (err) {
            const msg = err.response?.data?.detail || err.message;
            setAgentError(msg);
            showToast({ key: 'agent.writeFailed', values: { message: msg } }, 'error');
        } finally {
            setIsLoading(false);
        }
    };

    const handleYoutube = async () => {
        if (!youtubeUrl.trim()) {
            showToast({ key: 'agent.youtubeUrlRequired' }, 'warning');
            return;
        }
        beginRequest();
        try {
            const res = await client.post('/api/agent/youtube', {
                url: youtubeUrl,
                query: youtubeQuery || '영상 내용을 요약해줘',
            });
            setResult(res.data.analysis || res.data.summary || JSON.stringify(res.data, null, 2));
            setAgentMeta(res.data.meta || null);
            showToast({ key: 'agent.youtubeComplete' }, 'success');
        } catch (err) {
            const msg = err.response?.data?.detail || err.message;
            setAgentError(msg);
            showToast({ key: 'agent.youtubeFailed', values: { message: msg } }, 'error');
        } finally {
            setIsLoading(false);
        }
    };

    const TOOL_HANDLERS = { research: handleResearch, write: handleWrite, youtube: handleYoutube };

    return {
        activeTool,
        isLoading,
        result,
        agentError,
        agentMeta,
        changeTool: (id) => { setActiveTool(id); setResult(''); setAgentError(null); setAgentMeta(null); },
        submit: () => TOOL_HANDLERS[activeTool]?.(),
        copyResult: () => { navigator.clipboard.writeText(result); showToast({ key: 'agent.clipboardCopied' }, 'success'); },
        research: { researchTopic, deepMode, setResearchTopic, setDeepMode },
        write: { writeTopic, writeRawText, formatType, setWriteTopic, setWriteRawText, setFormatType },
        youtube: { youtubeUrl, youtubeQuery, setYoutubeUrl, setYoutubeQuery },
        t,
    };
}
