import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Upload, FileText, CheckCircle, Loader2 } from 'lucide-react';
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

    const handleFileChange = (event) => {
        if (event.target.files?.[0]) {
            setFile(event.target.files[0]);
        }
    };

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
                } catch (web3Err) {
                    console.warn('Web3 Transaction failed:', web3Err);
                    rewardMessage = t('uploadPaper.rewardDelayed');
                }
            } else if (!walletAddress) {
                rewardMessage = t('uploadPaper.rewardSkipped');
            }

            showToast({
                key: 'uploadPaper.uploadSuccess',
                values: { rewardMessage },
            }, 'success');

            setFile(null);
            setTitle('');
            setAuthors('');
            setAbstract('');
            setTermsAgreed(false);
            setUploadStatusText(t('uploadPaper.statusPreparing'));
        } catch (err) {
            if (err.name === 'CanceledError' || err.code === 'ERR_CANCELED') {
                console.log('Upload request was cancelled (component unmounted).');
                return;
            }
            console.error('Upload failed:', err);
            showToast(err.response?.data?.detail || t('uploadPaper.uploadFailed'), 'error');
        } finally {
            setIsUploading(false);
        }
    };

    return (
        <div className="p-4 sm:p-8 max-w-4xl mx-auto animate-fade-in">
            <div className="mb-8">
                <h1 className="text-3xl font-display font-bold text-white flex items-center gap-3">
                    <span className="p-2.5 rounded-xl bg-gradient-to-br from-blue-500/20 to-purple-500/20 text-blue-400">
                        <Upload className="w-6 h-6" />
                    </span>
                    {t('uploadPaper.title')}
                </h1>
                <p className="text-white/40 mt-2 ml-14">{t('uploadPaper.subtitle')}</p>
            </div>

            <Card glass className="shadow-2xl">
                <CardContent className="p-6 sm:p-8">
                    <form onSubmit={handleUpload} className="space-y-6">
                        <div className="border-2 border-dashed border-white/10 hover:border-primary/50 transition-colors rounded-xl p-8 text-center bg-black/20 relative">
                            <input
                                type="file"
                                accept=".pdf"
                                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                                onChange={handleFileChange}
                            />
                            {file ? (
                                <div className="flex flex-col items-center gap-3">
                                    <CheckCircle className="w-12 h-12 text-green-400" />
                                    <div>
                                        <p className="text-white font-medium">{file.name}</p>
                                        <p className="text-white/40 text-sm">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                                    </div>
                                </div>
                            ) : (
                                <div className="flex flex-col items-center gap-3 pointer-events-none">
                                    <FileText className="w-12 h-12 text-white/30" />
                                    <p className="text-white/60 font-medium">{t('uploadPaper.fileDropTitle')}</p>
                                    <p className="text-white/30 text-sm">{t('uploadPaper.fileDropDescription')}</p>
                                </div>
                            )}
                        </div>

                        <div className="grid gap-6">
                            <div>
                                <label className="block text-sm font-medium text-white/70 mb-2">{t('uploadPaper.titleLabel')}</label>
                                <Input
                                    type="text"
                                    variant="glass"
                                    value={title}
                                    onChange={(event) => setTitle(event.target.value)}
                                    placeholder={t('uploadPaper.titlePlaceholder')}
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-white/70 mb-2">{t('uploadPaper.authorsLabel')}</label>
                                <Input
                                    type="text"
                                    variant="glass"
                                    value={authors}
                                    onChange={(event) => setAuthors(event.target.value)}
                                    placeholder={t('uploadPaper.authorsPlaceholder')}
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-white/70 mb-2">{t('uploadPaper.abstractLabel')}</label>
                                <textarea
                                    value={abstract}
                                    onChange={(event) => setAbstract(event.target.value)}
                                    className="glass-input w-full h-32 resize-none"
                                    placeholder={t('uploadPaper.abstractPlaceholder')}
                                />
                            </div>
                        </div>

                        <div className="flex items-start gap-3 p-4 bg-primary/5 border border-primary/20 rounded-xl">
                            <div className="flex-shrink-0 mt-0.5">
                                <input
                                    type="checkbox"
                                    id="terms"
                                    checked={termsAgreed}
                                    onChange={(event) => setTermsAgreed(event.target.checked)}
                                    className="w-5 h-5 rounded border-white/20 bg-black/20 text-primary-500 focus:ring-primary-500/50"
                                />
                            </div>
                            <div>
                                <label htmlFor="terms" className="text-sm font-medium text-white/90 block cursor-pointer">
                                    {t('uploadPaper.agreementLabel')}
                                </label>
                                <p className="text-xs text-white/50 mt-1">
                                    {t('uploadPaper.agreementDescription')}
                                </p>
                            </div>
                        </div>

                        <div className="pt-4 flex justify-end">
                            <Button
                                type="submit"
                                disabled={isUploading || !file || !termsAgreed}
                                variant="ghost"
                                size="lg"
                                className="bg-primary/20 hover:bg-primary/30 text-primary-300 font-semibold px-8"
                            >
                                <AnimatePresence mode="wait">
                                    {isUploading ? (
                                        <motion.div
                                            key={uploadStatusText}
                                            initial={{ opacity: 0, y: 10 }}
                                            animate={{ opacity: 1, y: 0 }}
                                            exit={{ opacity: 0, y: -10 }}
                                            className="flex items-center gap-2"
                                        >
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                            <span>{uploadStatusText}</span>
                                        </motion.div>
                                    ) : (
                                        <motion.div
                                            key="upload-btn"
                                            initial={{ opacity: 0, y: 10 }}
                                            animate={{ opacity: 1, y: 0 }}
                                            exit={{ opacity: 0, y: -10 }}
                                            className="flex items-center gap-2"
                                        >
                                            <Upload className="w-4 h-4" />
                                            <span>{t('uploadPaper.submit')}</span>
                                        </motion.div>
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
