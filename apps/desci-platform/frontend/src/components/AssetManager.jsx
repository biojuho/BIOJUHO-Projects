import { useCallback, useEffect, useState } from 'react';
import { FileText, RefreshCw, Upload } from 'lucide-react';
import { useToast } from '../contexts/ToastContext';
import { useLocale } from '../contexts/LocaleContext';
import api from '../services/api';
import { Button } from './ui/Button';
import GlassCard from './ui/GlassCard';

export default function AssetManager() {
    const { showToast } = useToast();
    const { t } = useLocale();
    const [assets, setAssets] = useState([]);
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [selectedType, setSelectedType] = useState('ir');

    const assetTypes = [
        { value: 'ir', label: t('assetManager.typeIr') },
        { value: 'paper', label: t('assetManager.typePaper') },
        { value: 'patent', label: t('assetManager.typePatent') },
        { value: 'general', label: t('assetManager.typeGeneral') },
    ];

    const fetchAssets = useCallback(async () => {
        setLoading(true);
        try {
            const response = await api.get('/assets');
            setAssets(response.data);
        } catch (error) {
            console.error(error);
            showToast({ key: 'assetManager.loadFailed' }, 'error');
        } finally {
            setLoading(false);
        }
    }, [showToast]);

    useEffect(() => {
        fetchAssets();
    }, [fetchAssets]);

    const handleFileUpload = async (event) => {
        const file = event.target.files?.[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('file', file);
        formData.append('asset_type', selectedType);

        setUploading(true);
        try {
            await api.post('/assets/upload', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });
            showToast({ key: 'assetManager.uploadSuccess' }, 'success');
            fetchAssets();
        } catch (error) {
            console.error(error);
            showToast({ key: 'assetManager.uploadFailed' }, 'error');
        } finally {
            setUploading(false);
        }
    };

    return (
        <div className="space-y-6">
            <GlassCard className="p-7">
                <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
                    <div>
                        <p className="clay-chip mb-4">{t('layout.trust')}</p>
                        <h1 className="font-display text-4xl font-semibold text-ink">{t('assetManager.title')}</h1>
                        <p className="mt-3 text-sm leading-7 text-ink-muted">{t('assetManager.uploadDescription')}</p>
                    </div>
                    <Button onClick={fetchAssets} variant="outline">
                        <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                        {t('assetManager.refresh')}
                    </Button>
                </div>
            </GlassCard>

            <GlassCard className="p-7">
                <div className="flex flex-col items-center gap-4 text-center">
                    <div className="flex h-16 w-16 items-center justify-center rounded-full bg-white text-primary shadow-clay-soft">
                        <Upload className="h-7 w-7" />
                    </div>
                    <div>
                        <h2 className="font-display text-2xl font-semibold text-ink">{t('assetManager.uploadTitle')}</h2>
                        <p className="mt-2 text-sm leading-7 text-ink-muted">{t('assetManager.uploadDescription')}</p>
                    </div>
                    <div className="flex flex-col gap-3 sm:flex-row">
                        <select value={selectedType} onChange={(event) => setSelectedType(event.target.value)} className="clay-input">
                            {assetTypes.map((assetType) => (
                                <option key={assetType.value} value={assetType.value}>{assetType.label}</option>
                            ))}
                        </select>
                        <label className="clay-button clay-button-primary cursor-pointer justify-center text-white">
                            {uploading ? t('assetManager.uploading') : t('assetManager.selectFile')}
                            <input type="file" className="hidden" onChange={handleFileUpload} accept=".pdf,.txt" disabled={uploading} />
                        </label>
                    </div>
                </div>
            </GlassCard>

            <GlassCard className="p-7">
                <h2 className="mb-5 font-display text-2xl font-semibold text-ink">{t('assetManager.myAssets')} ({assets.length})</h2>

                {loading ? (
                    <div className="space-y-4">
                        {[1, 2, 3].map((index) => (
                            <div key={index} className="clay-panel-pressed h-24 rounded-[1.6rem] animate-pulse" />
                        ))}
                    </div>
                ) : assets.length === 0 ? (
                    <p className="text-sm text-ink-muted">{t('assetManager.empty')}</p>
                ) : (
                    <div className="space-y-3">
                        {assets.map((asset, index) => (
                            <div key={index} className="clay-panel-pressed flex flex-col gap-4 rounded-[1.6rem] p-5 md:flex-row md:items-center md:justify-between">
                                <div className="flex items-center gap-4">
                                    <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white text-primary shadow-clay-soft">
                                        <FileText className="h-5 w-5" />
                                    </div>
                                    <div>
                                        <p className="font-semibold text-ink">{asset.filename}</p>
                                        <p className="text-xs text-ink-muted">{asset.path}</p>
                                    </div>
                                </div>
                                <div className="flex flex-wrap gap-2">
                                    <span className="rounded-full bg-white/70 px-3 py-1 text-xs font-semibold text-ink-muted">
                                        IPFS: {asset.cid || t('assetManager.pending')}
                                    </span>
                                    <span className="rounded-full bg-primary/12 px-3 py-1 text-xs font-semibold text-primary">
                                        {t('assetManager.pinned')}
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </GlassCard>
        </div>
    );
}
