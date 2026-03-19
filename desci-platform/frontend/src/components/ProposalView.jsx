import { useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { motion } from 'framer-motion';
import { AlertTriangle, Copy, Download, ExternalLink, FileText, Sparkles, X } from 'lucide-react';
import { useToast } from '../contexts/ToastContext';
import { useLocale } from '../contexts/LocaleContext';

const ProposalView = ({ rfp, draft, critique, onClose }) => {
    const { showToast } = useToast();
    const { t } = useLocale();
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
                showToast({ key: 'proposal.popupBlocked' }, 'error');
                setExporting(false);
                return;
            }

            const safeTitle = String(title).replace(/[<>]/g, '');
            popup.document.open();
            popup.document.write(`
                <!doctype html>
                <html lang="en">
                  <head>
                    <meta charset="utf-8" />
                    <title>${safeTitle} - DSCI Proposal</title>
                    <style>
                      body {
                        font-family: "Georgia", serif;
                        margin: 40px auto;
                        max-width: 820px;
                        line-height: 1.7;
                        color: #2f3443;
                      }
                      .eyebrow {
                        color: #46ad92;
                        font-size: 12px;
                        font-weight: 700;
                        text-transform: uppercase;
                        letter-spacing: 0.18em;
                        margin-bottom: 24px;
                      }
                      h1 {
                        font-size: 30px;
                        margin-bottom: 20px;
                        border-bottom: 1px solid #d7cab9;
                        padding-bottom: 18px;
                      }
                      .content-body {
                        font-size: 15px;
                        white-space: pre-wrap;
                      }
                    </style>
                  </head>
                  <body>
                    <div class="eyebrow">DSCI Match Studio Proposal</div>
                    <h1>${safeTitle}</h1>
                    <div class="content-body">${element.innerHTML.replace(/<textarea[\s\S]*?<\/textarea>/g, '')}</div>
                  </body>
                </html>
            `);
            popup.document.close();
            popup.focus();
            setTimeout(() => {
                popup.print();
                setExporting(false);
            }, 500);
            showToast({ key: 'proposal.exportOpened' }, 'info');
        } catch {
            showToast({ key: 'proposal.exportFailed' }, 'error');
            setExporting(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#f2eadf]/70 p-4 backdrop-blur-md">
            <motion.div
                initial={{ opacity: 0, scale: 0.96, y: 12 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                className="glass-card flex max-h-[92vh] w-full max-w-5xl flex-col overflow-hidden"
            >
                <div className="flex items-start justify-between gap-4 border-b border-white/60 px-6 py-5">
                    <div>
                        <div className="mb-2 flex items-center gap-2 text-primary">
                            <Sparkles className="h-4 w-4" />
                            <span className="text-xs font-bold uppercase tracking-[0.18em]">{t('proposal.title')}</span>
                        </div>
                        <h2 className="font-display text-3xl font-semibold text-ink">{rfp?.metadata?.title || t('proposal.subtitle')}</h2>
                        <p className="mt-2 text-sm text-ink-muted">{t('proposal.subtitle')}</p>
                    </div>
                    <button onClick={onClose} className="clay-button h-11 w-11 !px-0">
                        <X className="h-4 w-4" />
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto px-6 py-6">
                    <div className="clay-panel-pressed mb-6 flex gap-4 rounded-[1.6rem] p-5">
                        <div className="rounded-full bg-highlight/20 p-2 text-highlight-dark">
                            <AlertTriangle className="h-5 w-5" />
                        </div>
                        <div>
                            <p className="text-sm font-semibold text-ink">{t('proposal.warningTitle')}</p>
                            <p className="mt-2 text-sm leading-7 text-ink-muted">{t('proposal.warningBody')}</p>
                        </div>
                    </div>

                    <div className="space-y-6" ref={contentRef}>
                        <div className="clay-panel rounded-[2rem] bg-white/70 p-8">
                            <div className="mb-5 flex items-center gap-2 text-ink-soft">
                                <FileText className="h-4 w-4" />
                                <span className="text-xs font-bold uppercase tracking-[0.18em]">{t('proposal.rawEditor')}</span>
                            </div>
                            <div className="prose max-w-none whitespace-pre-wrap prose-headings:font-display prose-headings:text-ink prose-p:text-ink-muted">
                                {draft}
                            </div>
                        </div>

                        {critique && (
                            <div className="glass-card p-6">
                                <p className="clay-chip mb-4">{t('proposal.peerReview')}</p>
                                <div className="prose max-w-none prose-headings:font-display prose-headings:text-ink prose-p:text-ink-muted">
                                    <ReactMarkdown>{critique}</ReactMarkdown>
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                <div className="flex flex-col gap-3 border-t border-white/60 px-6 py-5 sm:flex-row sm:justify-end">
                    <button
                        className="clay-button"
                        onClick={() => {
                            navigator.clipboard.writeText(draft);
                            showToast({ key: 'proposal.copied' }, 'success');
                        }}
                    >
                        <Copy className="h-4 w-4" />
                        {t('proposal.copyAll')}
                    </button>
                    <button onClick={handleExportPDF} disabled={exporting} className="clay-button clay-button-primary text-white">
                        {exporting ? <span>{t('proposal.exporting')}</span> : <><Download className="h-4 w-4" />{t('proposal.exportPdf')}</>}
                    </button>
                    <button onClick={onClose} className="clay-button">
                        <ExternalLink className="h-4 w-4" />
                        {t('proposal.close')}
                    </button>
                </div>
            </motion.div>
        </div>
    );
};

export default ProposalView;
