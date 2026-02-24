/**
 * ProposalView Component
 * Displays and allows editing of AI-generated proposal drafts.
 */
import React, { useRef, useState } from 'react';
import { useToast } from '../contexts/ToastContext';

import ReactMarkdown from 'react-markdown';

const ProposalView = ({ rfp, draft, critique, onClose }) => {
    const { showToast } = useToast();
    const contentRef = useRef(null);
    const [exporting, setExporting] = useState(false);

    const handleExportPDF = () => {
        const element = contentRef.current;
        if (!element) return;

        setExporting(true);
        try {
            const title = rfp?.metadata?.title || 'Draft';
            const popup = window.open('', '_blank', 'noopener,noreferrer,width=1024,height=1440');
            if (!popup) {
                showToast('팝업 차단을 해제한 뒤 다시 시도해주세요.', 'error');
                return;
            }

            const safeTitle = String(title).replace(/[<>]/g, '');
            popup.document.open();
            popup.document.write(`
                <!doctype html>
                <html lang="ko">
                  <head>
                    <meta charset="utf-8" />
                    <title>${safeTitle}</title>
                    <style>
                      body { font-family: "Noto Sans KR", Arial, sans-serif; margin: 32px; line-height: 1.55; color: #111; }
                      h1 { border-bottom: 1px solid #ddd; padding-bottom: 12px; margin-bottom: 20px; }
                      @media print { body { margin: 16mm; } }
                    </style>
                  </head>
                  <body>
                    <h1>${safeTitle}</h1>
                    ${element.innerHTML}
                  </body>
                </html>
            `);
            popup.document.close();
            popup.focus();
            setTimeout(() => popup.print(), 250);
            showToast('인쇄 창을 열었습니다. PDF로 저장하세요.', 'info');
        } catch {
            showToast('PDF 저장 준비 중 오류가 발생했습니다.', 'error');
        } finally {
            setExporting(false);
        }
    };

    return (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-surface border border-white/[0.08] rounded-2xl w-full max-w-4xl max-h-[90vh] flex flex-col animate-fade-in-up" style={{ boxShadow: '0 32px 64px rgba(0,0,0,0.6)' }}>
                {/* Header */}
                <div className="p-6 border-b border-white/[0.06] flex justify-between items-center bg-white/[0.02] rounded-t-2xl">
                    <div>
                        <h2 className="font-display text-2xl font-bold text-gradient">
                            📜 BioLinker AI 연구 제안서
                        </h2>
                        <p className="text-gray-400 text-sm mt-1">
                            대상 공고: <span className="text-white">{rfp.metadata.title}</span>
                        </p>
                    </div>
                    <button
                        onClick={onClose}
                        className="text-white/30 hover:text-white transition-colors p-2 hover:bg-white/[0.06] rounded-lg"
                    >
                        ✕
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-auto p-6 bg-surface custom-scrollbar">
                    {/* Legal Disclaimer */}
                    <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-4 mb-6">
                        <div className="flex items-start gap-3">
                            <span className="text-2xl">⚠️</span>
                            <div>
                                <h4 className="text-yellow-200 font-bold text-sm mb-1">AI 생성 콘텐츠 주의사항</h4>
                                <p className="text-yellow-100/70 text-xs leading-relaxed">
                                    본 제안서는 BioLinker AI가 생성한 초안입니다. 내용의 정확성을 보장하지 않으며,
                                    실제 제출 전 반드시 사용자 검토 및 수정이 필요합니다. 회사는 결과물에 대한 법적 책임을 지지 않습니다.
                                </p>
                            </div>
                        </div>
                    </div>

                    <div className="prose prose-invert max-w-none" ref={contentRef}>
                        <div className="p-8 bg-white text-black rounded-lg whitespace-pre-wrap font-serif min-h-[50vh]">
                            {/* PDF Export Content Container */}
                            <h1 className="text-2xl font-bold mb-6 text-center border-b pb-4">
                                {rfp.metadata.title || 'Research Proposal'}
                            </h1>
                            {draft}
                        </div>

                        {/* AI Peer Review Section */}
                        {critique && (
                            <div className="mt-8 bg-accent/[0.08] border border-accent/20 rounded-xl p-6">
                                <h3 className="font-display text-xl font-bold text-white mb-4 flex items-center gap-2">
                                    <span>🤖</span> AI Peer Review
                                </h3>
                                <div className="prose prose-invert max-w-none font-sans text-white/60">
                                    <ReactMarkdown>{critique}</ReactMarkdown>
                                </div>
                            </div>
                        )}

                        {/* Interactive Textarea for UI viewing/editing */}
                        <textarea
                            className="w-full h-[30vh] mt-6 bg-transparent border-none text-white/60 resize-none focus:ring-0 font-mono leading-relaxed p-0 border-t border-white/[0.06] pt-4"
                            value={draft}
                            readOnly
                        />
                    </div>
                </div>

                {/* Footer */}
                <div className="p-6 border-t border-white/[0.06] bg-white/[0.02] rounded-b-2xl flex justify-end gap-3">
                    <button
                        onClick={onClose}
                        className="px-5 py-2.5 text-white/50 hover:bg-white/[0.04] rounded-xl transition-colors font-medium"
                    >
                        닫기
                    </button>
                    <button
                        onClick={handleExportPDF}
                        disabled={exporting}
                        className="px-5 py-2.5 bg-accent/[0.12] text-accent-light font-bold rounded-xl hover:bg-accent/25 transition-all flex items-center gap-2 border border-accent/20"
                    >
                        {exporting ? '저장 중...' : '📄 PDF 저장'}
                    </button>
                    <button
                        className="glass-button px-6 py-2.5 font-bold flex items-center gap-2"
                        onClick={() => {
                            navigator.clipboard.writeText(draft);
                            showToast('클립보드에 복사되었습니다! ✨', 'success');
                        }}
                    >
                        <span>📋 전체 복사</span>
                    </button>
                </div>
            </div>
        </div>
    );
};

export default ProposalView;
