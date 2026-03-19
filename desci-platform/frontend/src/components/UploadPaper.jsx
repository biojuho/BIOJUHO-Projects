import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { CheckCircle, FileText, Loader2, Upload } from 'lucide-react';
import { useToast } from '../contexts/ToastContext';
import { useAuth } from '../contexts/AuthContext';
import { useLocale } from '../contexts/LocaleContext';
import api from '../services/api';
import { Card, CardContent } from './ui/Card';
import { Button } from './ui/Button';
import { Input } from './ui/Input';

export default function UploadPaper() {
    const [file, setFile] = useState(null);
    const [title, setTitle] = useState('');
    const [authors, setAuthors] = useState('');
    const [abstract, setAbstract] = useState('');
    const [isUploading, setIsUploading] = useState(false);
    const [uploadStatusText, setUploadStatusText] = useState('');
    const [termsAgreed, setTermsAgreed] = useState(false);
    const abortControllerRef = useRef(null);
    const { showToast } = useToast();
    const { walletAddress } = useAuth();
    const { t } = useLocale();

    useEffect(() => {
        setUploadStatusText(t('uploadPaper.statusPreparing'));
    }, [t]);

    useEffect(() => () => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
    }, []);

    const handleUpload = async (event) => {
        event.preventDefault();
        if (!file || !title || !authors) {
            showToast({ key: 'uploadPaper.validationRequired' }, 'warning');
            return;
        }
        if (!termsAgreed) {
            showToast({ key: 'uploadPaper.validationTerms' }, 'warning');
            return;
        }

        setIsUploading(true);
        setUploadStatusText(t('uploadPaper.statusUploading'));
        abortControllerRef.current = new AbortController();

        const formData = new FormData();
        formData.append('file', file);
        formData.append('title', title);
        formData.append('abstract', abstract);
        formData.append('authors', authors);

        try {
            const response = await api.post('/upload', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
                signal: abortControllerRef.current.signal,
            });
            const result = response.data;

            let rewardMessage = '';
            if (walletAddress && result.cid) {
                try {
                    const consentTimestamp = new Date().toISOString();
                    const consentPayload = `consent:${consentTimestamp}|wallet:${walletAddress}|cid:${result.cid}|terms:CC-BY-4.0`;
                    const encoder = new TextEncoder();
                    const hashBuffer = await crypto.subtle.digest('SHA-256', encoder.encode(consentPayload));
                    const consentHash = `0x${Array.from(new Uint8Array(hashBuffer)).map((byte) => byte.toString(16).padStart(2, '0')).join('')}`;

                    setUploadStatusText(t('uploadPaper.statusMinting'));
                    await api.post('/nft/mint', {
                        user_address: walletAddress,
                        token_uri: `ipfs://${result.cid}`,
                        consent_hash: consentHash,
                        consent_timestamp: consentTimestamp,
                    });

                    setUploadStatusText(t('uploadPaper.statusRewarding'));
                    await api.post(`/reward/paper?user_address=${walletAddress}`);
                    rewardMessage = t('uploadPaper.rewardSuccess');
                } catch {
                    rewardMessage = t('uploadPaper.rewardDelayed');
                }
            } else if (!walletAddress) {
                rewardMessage = t('uploadPaper.rewardSkipped');
            }

            showToast({ key: 'uploadPaper.uploadSuccess', values: { rewardMessage } }, 'success');
            setFile(null);
            setTitle('');
            setAuthors('');
            setAbstract('');
            setTermsAgreed(false);
            setUploadStatusText(t('uploadPaper.statusPreparing'));
        } catch (err) {
            if (err.name === 'CanceledError' || err.code === 'ERR_CANCELED') return;
            showToast(err.response?.data?.detail || t('uploadPaper.uploadFailed'), 'error');
        } finally {
            setIsUploading(false);
        }
    };

    return (
        <div className="space-y-6">
            <Card glass className="p-7">
                <CardContent className="p-0">
                    <p className="clay-chip mb-4">{t('layout.workspace')}</p>
                    <h1 className="font-display text-4xl font-semibold text-ink">{t('uploadPaper.title')}</h1>
                    <p className="mt-3 text-sm leading-7 text-ink-muted">{t('uploadPaper.subtitle')}</p>
                </CardContent>
            </Card>

            <Card glass className="shadow-clay p-0">
                <CardContent className="p-6 sm:p-8">
                    <form onSubmit={handleUpload} className="space-y-6">
                        <label className="glass-card block cursor-pointer p-8 text-center">
                            <input type="file" accept=".pdf" className="hidden" onChange={(event) => setFile(event.target.files?.[0] || null)} />
                            {file ? (
                                <div className="flex flex-col items-center gap-3">
                                    <CheckCircle className="h-12 w-12 text-success" />
                                    <div>
                                        <p className="font-semibold text-ink">{file.name}</p>
                                        <p className="text-sm text-ink-muted">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                                    </div>
                                </div>
                            ) : (
                                <div className="flex flex-col items-center gap-3">
                                    <div className="flex h-16 w-16 items-center justify-center rounded-full bg-white text-primary shadow-clay-soft">
                                        <FileText className="h-8 w-8" />
                                    </div>
                                    <p className="font-semibold text-ink">{t('uploadPaper.fileDropTitle')}</p>
                                    <p className="text-sm text-ink-muted">{t('uploadPaper.fileDropDescription')}</p>
                                </div>
                            )}
                        </label>

                        <div className="grid gap-5">
                            <div>
                                <label className="mb-2 block text-sm font-semibold text-ink">{t('uploadPaper.titleLabel')}</label>
                                <Input type="text" value={title} onChange={(event) => setTitle(event.target.value)} placeholder={t('uploadPaper.titlePlaceholder')} />
                            </div>
                            <div>
                                <label className="mb-2 block text-sm font-semibold text-ink">{t('uploadPaper.authorsLabel')}</label>
                                <Input type="text" value={authors} onChange={(event) => setAuthors(event.target.value)} placeholder={t('uploadPaper.authorsPlaceholder')} />
                            </div>
                            <div>
                                <label className="mb-2 block text-sm font-semibold text-ink">{t('uploadPaper.abstractLabel')}</label>
                                <textarea value={abstract} onChange={(event) => setAbstract(event.target.value)} className="clay-input min-h-[180px] resize-none" placeholder={t('uploadPaper.abstractPlaceholder')} />
                            </div>
                        </div>

                        <label className="clay-panel-pressed flex items-start gap-3 rounded-[1.6rem] p-4">
                            <input type="checkbox" checked={termsAgreed} onChange={(event) => setTermsAgreed(event.target.checked)} className="mt-1" />
                            <div>
                                <span className="block text-sm font-semibold text-ink">{t('uploadPaper.agreementLabel')}</span>
                                <span className="mt-1 block text-xs leading-6 text-ink-muted">{t('uploadPaper.agreementDescription')}</span>
                            </div>
                        </label>

                        <div className="flex justify-end">
                            <Button type="submit" disabled={isUploading || !file || !termsAgreed} size="lg" className="justify-center text-white">
                                <AnimatePresence mode="wait">
                                    {isUploading ? (
                                        <motion.span key={uploadStatusText} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex items-center gap-2">
                                            <Loader2 className="h-4 w-4 animate-spin" />
                                            {uploadStatusText}
                                        </motion.span>
                                    ) : (
                                        <motion.span key="upload-label" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex items-center gap-2">
                                            <Upload className="h-4 w-4" />
                                            {t('uploadPaper.submit')}
                                        </motion.span>
                                    )}
                                </AnimatePresence>
                            </Button>
                        </div>
                    </form>
                </CardContent>
            </Card>
        </div>
    );
}
