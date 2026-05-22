import { useCallback, useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { CheckCircle, FileText, Loader2, Upload, Sparkles } from 'lucide-react';
import { useToast } from '../contexts/ToastContext';
import { useAuth } from '../contexts/AuthContext';
import { useLocale } from '../contexts/LocaleContext';
import { useJobProgress } from '../hooks/useJobProgress';
import api from '../services/api';
import { formatSupportError } from '../lib/support';
import { Card, CardContent } from './ui/Card';
import { Button } from './ui/Button';
import { Input } from './ui/Input';
import JobProgressPanel from './JobProgressPanel';

export default function UploadPaper() {
    const [file, setFile] = useState(null);
    const [title, setTitle] = useState('');
    const [authors, setAuthors] = useState('');
    const [abstract, setAbstract] = useState('');
    const [isUploading, setIsUploading] = useState(false);
    const { t } = useLocale();
    const [uploadStatusText, setUploadStatusText] = useState(() => t('uploadPaper.statusPreparing'));
    const [termsAgreed, setTermsAgreed] = useState(false);
    const [mintTxHash, setMintTxHash] = useState(null);
    const [rewardTxHash, setRewardTxHash] = useState(null);
    const abortControllerRef = useRef(null);
    const { showToast } = useToast();
    const { walletAddress } = useAuth();
    const { job: jobStatus, watchJob, clearJob } = useJobProgress();

    useEffect(() => () => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
    }, []);

    const text = useCallback((key, fallback, values) => {
        const message = t(key, values);
        return message === key ? fallback : message;
    }, [t]);

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
        clearJob();
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
            let result = response.data;

            if (result.id || result.cid) {
                setUploadStatusText(text('uploadPaper.statusIndexing', 'Parsing and indexing the paper...'));
                const indexResponse = await api.post('/jobs/papers/index', { paper_id: result.id || result.cid });
                const job = indexResponse.data?.job;
                if (!job?.id) {
                    throw new Error('Paper indexing job was not created.');
                }
                const indexResult = await watchJob(job);
                result = {
                    ...result,
                    ...indexResult,
                    cid: result.cid || indexResult.cid,
                    ipfs_url: result.ipfs_url || indexResult.ipfs_url,
                };
            }

            let rewardMessage = '';
            if (walletAddress && result.cid) {
                try {
                    const consentTimestamp = new Date().toISOString();
                    const consentPayload = `consent:${consentTimestamp}|wallet:${walletAddress}|cid:${result.cid}|terms:CC-BY-4.0`;
                    const encoder = new TextEncoder();
                    const hashBuffer = await crypto.subtle.digest('SHA-256', encoder.encode(consentPayload));
                    const consentHash = `0x${Array.from(new Uint8Array(hashBuffer)).map((byte) => byte.toString(16).padStart(2, '0')).join('')}`;

                    setUploadStatusText(t('uploadPaper.statusMinting'));
                    const mintResponse = await api.post('/nft/mint', {
                        user_address: walletAddress,
                        token_uri: `ipfs://${result.cid}`,
                        consent_hash: consentHash,
                        consent_timestamp: consentTimestamp,
                    });
                    if (mintResponse.data?.tx_hash) {
                        setMintTxHash(mintResponse.data.tx_hash);
                    }

                    setUploadStatusText(t('uploadPaper.statusRewarding'));
                    const rewardResponse = await api.post(`/reward/paper?user_address=${walletAddress}`);
                    if (rewardResponse.data?.tx_hash) {
                        setRewardTxHash(rewardResponse.data.tx_hash);
                    }
                    rewardMessage = t('uploadPaper.rewardSuccess');
                } catch {
                    rewardMessage = t('uploadPaper.rewardDelayed');
                }
            } else if (!walletAddress) {
                rewardMessage = t('uploadPaper.rewardSkipped');
            }

            showToast({ key: 'uploadPaper.uploadSuccess', values: { rewardMessage } }, 'success');
            // Keep status hashes visible for a moment or show in success UI
            setTimeout(() => {
                setFile(null);
                setTitle('');
                setAuthors('');
                setAbstract('');
                setTermsAgreed(false);
                setUploadStatusText(t('uploadPaper.statusPreparing'));
                setMintTxHash(null);
                setRewardTxHash(null);
                clearJob();
            }, 5000);
        } catch (err) {
            if (err.name === 'AbortError' || err.name === 'CanceledError' || err.code === 'ERR_CANCELED') return;
            showToast(formatSupportError(err, t('uploadPaper.uploadFailed')), 'error');
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

            {jobStatus && (
                <JobProgressPanel
                    job={jobStatus}
                    title={text('uploadPaper.indexProgress', 'Indexing progress')}
                    icon={false}
                />
            )}

            {(mintTxHash || rewardTxHash) && (
                <motion.div 
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    className="glass-card overflow-hidden border-primary/20 bg-primary/5 p-5"
                >
                    <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-primary">
                        <Sparkles className="h-4 w-4" />
                        On-chain Confirmation
                    </h3>
                    <div className="space-y-3">
                        {mintTxHash && (
                            <div className="flex items-center justify-between text-xs">
                                <span className="text-ink-muted">IP-NFT Minted:</span>
                                <a 
                                    href={`https://amoy.polygonscan.com/tx/${mintTxHash}`} 
                                    target="_blank" 
                                    rel="noreferrer"
                                    className="font-mono text-primary hover:underline"
                                >
                                    {mintTxHash.slice(0, 10)}...{mintTxHash.slice(-8)}
                                </a>
                            </div>
                        )}
                        {rewardTxHash && (
                            <div className="flex items-center justify-between text-xs">
                                <span className="text-ink-muted">DSCI Rewards:</span>
                                <a 
                                    href={`https://amoy.polygonscan.com/tx/${rewardTxHash}`} 
                                    target="_blank" 
                                    rel="noreferrer"
                                    className="font-mono text-primary hover:underline"
                                >
                                    {rewardTxHash.slice(0, 10)}...{rewardTxHash.slice(-8)}
                                </a>
                            </div>
                        )}
                    </div>
                </motion.div>
            )}

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
