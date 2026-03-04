import { useCallback, useEffect, useState } from 'react';
import { Upload, FileText, RefreshCw } from 'lucide-react';
import { useToast } from '../contexts/ToastContext';
import { useLocale } from '../contexts/LocaleContext';
import api from '../services/api';

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
        if (!file) {
            return;
        }

        const formData = new FormData();
        formData.append('file', file);
        formData.append('asset_type', selectedType);

        setUploading(true);
        try {
            await api.post('/assets/upload', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
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
        <div className="bg-black/40 backdrop-blur-xl border border-white/10 rounded-2xl p-6">
            <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold text-white flex items-center gap-2">
                    <FileText className="text-primary" /> {t('assetManager.title')}
                </h2>
                <button
                    onClick={fetchAssets}
                    className="p-2 text-gray-400 hover:text-white transition-colors"
                >
                    <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
                </button>
            </div>

            <div className="mb-8 p-6 border-2 border-dashed border-white/20 rounded-xl hover:border-primary/50 transition-colors bg-white/5">
                <div className="flex flex-col items-center justify-center gap-4">
                    <div className="p-4 bg-primary/20 rounded-full">
                        <Upload className="w-8 h-8 text-primary" />
                    </div>
                    <div className="text-center">
                        <h3 className="text-lg font-medium text-white">{t('assetManager.uploadTitle')}</h3>
                        <p className="text-sm text-gray-400">{t('assetManager.uploadDescription')}</p>
                    </div>

                    <div className="flex items-center gap-3">
                        <select
                            value={selectedType}
                            onChange={(event) => setSelectedType(event.target.value)}
                            className="bg-black/50 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                        >
                            {assetTypes.map((assetType) => (
                                <option key={assetType.value} value={assetType.value}>{assetType.label}</option>
                            ))}
                        </select>

                        <label className="cursor-pointer bg-primary hover:bg-primary/80 text-white px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2">
                            {uploading ? t('assetManager.uploading') : t('assetManager.selectFile')}
                            <input
                                type="file"
                                className="hidden"
                                onChange={handleFileUpload}
                                accept=".pdf,.txt"
                                disabled={uploading}
                            />
                        </label>
                    </div>
                </div>
            </div>

            <div className="space-y-3">
                <h3 className="text-lg font-semibold text-white mb-4">{t('assetManager.myAssets')} ({assets.length})</h3>

                {loading ? (
                    <div className="space-y-4 animate-pulse">
                        {[1, 2, 3].map((index) => (
                            <div key={index} className="flex items-center gap-4 p-4 bg-white/5 rounded-xl border border-white/5">
                                <div className="w-8 h-8 rounded-lg bg-white/10"></div>
                                <div className="flex-1 space-y-2">
                                    <div className="h-4 bg-white/10 rounded w-1/3"></div>
                                    <div className="h-3 bg-white/10 rounded w-1/4"></div>
                                    <div className="flex gap-2 mt-2">
                                        <div className="h-5 w-24 bg-white/10 rounded-md"></div>
                                        <div className="h-5 w-16 bg-white/10 rounded-md"></div>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                ) : assets.length === 0 ? (
                    <div className="text-center py-8 text-gray-500">
                        {t('assetManager.empty')}
                    </div>
                ) : (
                    assets.map((asset, index) => (
                        <div key={index} className="flex items-center justify-between p-4 bg-white/5 rounded-xl border border-white/5">
                            <div className="flex items-center gap-4">
                                <FileText className="w-8 h-8 text-secondary" />
                                <div>
                                    <p className="font-medium text-white">{asset.filename}</p>
                                    <p className="text-xs text-gray-400">{asset.path}</p>
                                    <div className="mt-2 flex flex-wrap items-center gap-2">
                                        <span className="px-2 py-1 bg-green-500/10 text-green-400 text-xs rounded-md border border-green-500/20 font-mono truncate max-w-[200px] sm:max-w-none">
                                            IPFS: {asset.cid || t('assetManager.pending')}
                                        </span>
                                        <span className="px-2 py-1 bg-blue-500/10 text-blue-400 text-xs rounded-md border border-blue-500/20 tracking-wide">
                                            {t('assetManager.pinned')}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}
