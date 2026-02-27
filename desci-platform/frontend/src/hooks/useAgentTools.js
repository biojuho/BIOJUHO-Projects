import { useState } from 'react';
import client from '../services/api';
import { useToast } from '../contexts/ToastContext';

/**
 * @typedef {'research' | 'write' | 'youtube'} ToolId
 */

/**
 * @typedef {Object} ResearchInputs
 * @property {string} researchTopic
 * @property {boolean} deepMode
 * @property {(v: string) => void} setResearchTopic
 * @property {(v: boolean) => void} setDeepMode
 */

/**
 * @typedef {Object} WriteInputs
 * @property {string} writeTopic
 * @property {string} writeRawText
 * @property {string} formatType
 * @property {(v: string) => void} setWriteTopic
 * @property {(v: string) => void} setWriteRawText
 * @property {(v: string) => void} setFormatType
 */

/**
 * @typedef {Object} YoutubeInputs
 * @property {string} youtubeUrl
 * @property {string} youtubeQuery
 * @property {(v: string) => void} setYoutubeUrl
 * @property {(v: string) => void} setYoutubeQuery
 */

/**
 * @typedef {Object} UseAgentToolsReturn
 * @property {ToolId} activeTool
 * @property {boolean} isLoading
 * @property {string} result
 * @property {string | null} agentError
 * @property {(id: ToolId) => void} changeTool
 * @property {() => void} submit
 * @property {() => void} copyResult
 * @property {ResearchInputs} research
 * @property {WriteInputs} write
 * @property {YoutubeInputs} youtube
 */

/** @returns {UseAgentToolsReturn} */
export function useAgentTools() {
    const { showToast } = useToast();

    const [activeTool, setActiveTool] = useState(/** @type {ToolId} */ ('research'));
    const [isLoading, setIsLoading] = useState(false);
    const [result, setResult] = useState('');
    const [agentError, setAgentError] = useState(/** @type {string | null} */ (null));

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
    };

    const handleResearch = async () => {
        if (!researchTopic.trim()) {
            showToast('연구 주제를 입력해주세요.', 'warning');
            return;
        }
        beginRequest();
        try {
            const res = await client.post('/api/agent/research', { topic: researchTopic, deep: deepMode });
            setResult(res.data.result?.report || res.data.report || JSON.stringify(res.data, null, 2));
            showToast('연구 리포트 생성 완료!', 'success');
        } catch (err) {
            const msg = err.response?.data?.detail || err.message;
            setAgentError(msg);
            showToast(`연구 실패: ${msg}`, 'error');
        } finally {
            setIsLoading(false);
        }
    };

    const handleWrite = async () => {
        if (!writeTopic.trim() || !writeRawText.trim()) {
            showToast('주제와 원본 텍스트를 모두 입력해주세요.', 'warning');
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
            showToast('콘텐츠 생성 완료!', 'success');
        } catch (err) {
            const msg = err.response?.data?.detail || err.message;
            setAgentError(msg);
            showToast(`콘텐츠 생성 실패: ${msg}`, 'error');
        } finally {
            setIsLoading(false);
        }
    };

    const handleYoutube = async () => {
        if (!youtubeUrl.trim()) {
            showToast('YouTube URL을 입력해주세요.', 'warning');
            return;
        }
        beginRequest();
        try {
            const res = await client.post('/api/agent/youtube', {
                url: youtubeUrl,
                query: youtubeQuery || 'Summarize the video',
            });
            setResult(res.data.analysis || res.data.summary || JSON.stringify(res.data, null, 2));
            showToast('영상 분석 완료!', 'success');
        } catch (err) {
            const msg = err.response?.data?.detail || err.message;
            setAgentError(msg);
            showToast(`영상 분석 실패: ${msg}`, 'error');
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
        changeTool: (id) => { setActiveTool(id); setResult(''); setAgentError(null); },
        submit: () => TOOL_HANDLERS[activeTool]?.(),
        copyResult: () => { navigator.clipboard.writeText(result); showToast('클립보드에 복사되었습니다!', 'success'); },
        research: { researchTopic, deepMode, setResearchTopic, setDeepMode },
        write: { writeTopic, writeRawText, formatType, setWriteTopic, setWriteRawText, setFormatType },
        youtube: { youtubeUrl, youtubeQuery, setYoutubeUrl, setYoutubeQuery },
    };
}
