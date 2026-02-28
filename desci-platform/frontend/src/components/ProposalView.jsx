/**
 * ProposalView Component
 * Displays and allows editing of AI-generated proposal drafts with premium Glassmorphism.
 */
import React, { useRef, useState } from 'react';
import { useToast } from '../contexts/ToastContext';
import ReactMarkdown from 'react-markdown';
import { Sparkles, Download, Copy, X, FileText, AlertTriangle } from 'lucide-react';

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
                setExporting(false); // Ensure exporting state is reset
                return;
            }

            const safeTitle = String(title).replace(/[<>]/g, '');
            popup.document.open();
            popup.document.write(`
                <!doctype html>
                <html lang="ko">
                  <head>
                    <meta charset="utf-8" />
                    <title>${safeTitle} - BioLinker AI Proposal</title>
                    <style>
                      @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@300;400;500;600;700&display=swap');
                      body { 
                        font-family: "Pretendard", -apple-system, sans-serif; 
                        margin: 40px auto; 
                        max-width: 800px;
                        line-height: 1.6; 
                        color: #1a1a1a; 
                      }
                      .header-branding {
                        color: #6366f1;
                        font-size: 14px;
                        font-weight: 600;
                        margin-bottom: 24px;
                        text-transform: uppercase;
                        letter-spacing: 0.05em;
                      }
                      h1 { 
                        border-bottom: 2px solid #e5e7eb; 
                        padding-bottom: 16px; 
                        margin-bottom: 24px; 
                        font-size: 28px;
                        color: #111827;
                      }
                      .content-body {
                        font-size: 15px;
                        white-space: pre-wrap;
                      }
                      @media print { 
                        body { margin: 20mm; } 
                        .no-print { display: none; }
                      }
                    </style>
                  </head>
                  <body>
                    <div class="header-branding">BioLinker AI-Generated Proposal</div>
                    <h1>${safeTitle}</h1>
                    <div class="content-body">
                      ${element.innerHTML.replace(/<textarea[\s\S]*?<\/textarea>/g, '')}
                    </div>
                  </body>
                </html>
            `);
            popup.document.close();
            popup.focus();
            setTimeout(() => {
                popup.print();
                setExporting(false);
            }, 500);
            showToast('인쇄 창을 열었습니다. PDF로 저장하세요.', 'info');
        } catch {
            showToast('PDF 저장 준비 중 오류가 발생했습니다.', 'error');
            setExporting(false);
        }
    };

    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-md z-50 flex items-center justify-center p-4 sm:p-6 animate-in fade-in duration-300">
            <div 
                className="bg-slate-900/80 backdrop-blur-xl border border-white/10 rounded-3xl w-full max-w-5xl max-h-[90vh] flex flex-col shadow-2xl shadow-indigo-500/10 overflow-hidden"
                style={{ transform: 'translateZ(0)' }}
            >
                {/* Premium Header */}
                <div className="p-6 sm:px-8 border-b border-white/10 bg-gradient-to-r from-indigo-500/10 via-purple-500/10 to-transparent flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                    <div>
                        <div className="flex items-center gap-2 mb-1">
                            <Sparkles className="w-5 h-5 text-indigo-400" />
                            <h2 className="text-xl sm:text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-indigo-200 to-white">
                                AI 연구 제안서 초안
                            </h2>
                        </div>
                        <p className="text-indigo-200/60 text-sm font-medium flex items-center gap-2">
                            <FileText className="w-4 h-4" /> 
                            {rfp?.metadata?.title || 'Unknown RFP'}
                        </p>
                    </div>
                    <button
                        onClick={onClose}
                        className="text-slate-400 hover:text-white transition-all p-2 hover:bg-white/10 rounded-full bg-slate-800/50 absolute top-4 right-4 md:static"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Content Area */}
                <div className="flex-1 overflow-y-auto p-6 sm:p-8 custom-scrollbar relative">
                    {/* Legal Disclaimer Bubble */}
                    <div className="bg-amber-500/10 border border-amber-500/20 rounded-2xl p-4 sm:p-5 mb-8 flex items-start gap-4">
                        <div className="bg-amber-500/20 p-2 rounded-lg shrink-0 mt-0.5">
                            <AlertTriangle className="w-5 h-5 text-amber-400" />
                        </div>
                        <div>
                            <h4 className="text-amber-300 font-bold text-sm mb-1">AI 생성 콘텐츠 주의사항</h4>
                            <p className="text-amber-200/70 text-sm leading-relaxed">
                                본 제안서는 BioLinker AI가 작성한 초안으로, 내용의 완벽성과 학술적 정확성을 최종 보장하지 않습니다. 실제 제출 전 반드시 연구자의 면밀한 검토 및 수정 과정을 거치시기 바랍니다.
                            </p>
                        </div>
                    </div>

                    <div className="space-y-8" ref={contentRef}>
                        {/* The Actual Draft */}
                        <div className="bg-slate-50 border border-slate-200 rounded-2xl p-6 sm:p-10 shadow-inner">
                            <div className="prose prose-slate max-w-none">
                                <h1 className="text-3xl font-bold text-slate-900 mb-8 pb-4 border-b border-slate-200 text-center">
                                    {rfp?.metadata?.title || 'Research Proposal'}
                                </h1>
                                <div className="text-slate-800 font-serif leading-loose whitespace-pre-wrap text-[15px]">
                                    {draft}
                                </div>
                            </div>
                        </div>

                        {/* Editable Raw Fallback (for easy copy-pasting/minor edits directly in modal) */}
                        <div className="group relative">
                            <div className="absolute -inset-0.5 bg-gradient-to-r from-indigo-500/30 to-purple-500/30 rounded-2xl blur opacity-30 group-hover:opacity-60 transition duration-500"></div>
                            <div className="relative bg-slate-900 border border-slate-700 rounded-2xl p-4">
                                <div className="flex justify-between items-center mb-3 px-2">
                                    <span className="text-xs font-bold text-indigo-400 uppercase tracking-wider">Raw Editor Editor</span>
                                </div>
                                <textarea
                                    className="w-full h-48 bg-transparent text-slate-300 font-mono text-sm leading-relaxed border-none focus:ring-0 resize-y p-2 custom-scrollbar outline-none"
                                    value={draft}
                                    readOnly
                                />
                            </div>
                        </div>

                        {/* AI Peer Review Section */}
                        {critique && (
                            <div className="bg-indigo-900/20 border border-indigo-500/30 rounded-2xl p-6 sm:p-8 mt-12 relative overflow-hidden">
                                <div className="absolute top-0 right-0 p-8 opacity-5">
                                    <Sparkles className="w-32 h-32" />
                                </div>
                                <h3 className="text-xl font-bold text-indigo-300 mb-6 flex items-center gap-2">
                                    <div className="bg-indigo-500/20 p-2 rounded-lg">🤖</div>
                                    AI Peer Review Insights
                                </h3>
                                <div className="prose prose-invert prose-indigo max-w-none text-slate-300 font-sans text-[15px] leading-relaxed relative z-10">
                                    <ReactMarkdown>{critique}</ReactMarkdown>
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Footer Actions */}
                <div className="p-6 border-t border-white/10 bg-slate-900/50 backdrop-blur-md flex flex-col sm:flex-row justify-end gap-3 rounded-b-3xl shrink-0">
                    <button
                        onClick={onClose}
                        className="px-6 py-2.5 text-slate-300 hover:text-white hover:bg-white/5 rounded-xl transition-all font-medium border border-transparent hover:border-white/10"
                    >
                        닫기
                    </button>
                    
                    <button
                        className="px-6 py-2.5 bg-slate-800 text-slate-200 font-bold rounded-xl hover:bg-slate-700 transition-all flex items-center justify-center gap-2 border border-slate-600 shadow-sm"
                        onClick={() => {
                            navigator.clipboard.writeText(draft);
                            showToast('전체 내용이 클립보드에 복사되었습니다!', 'success');
                        }}
                    >
                        <Copy className="w-4 h-4" />
                        <span>전체 복사</span>
                    </button>

                    <button
                        onClick={handleExportPDF}
                        disabled={exporting}
                        className="px-6 py-2.5 bg-gradient-to-r from-indigo-500 to-purple-500 text-white font-bold rounded-xl hover:from-indigo-400 hover:to-purple-400 transition-all flex items-center justify-center gap-2 shadow-lg shadow-indigo-500/25 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {exporting ? (
                            <span className="animate-pulse">준비 중...</span>
                        ) : (
                            <>
                                <Download className="w-4 h-4" />
                                <span>PDF 내보내기</span>
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default ProposalView;
