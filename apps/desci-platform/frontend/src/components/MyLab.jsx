import { Link } from 'react-router-dom';
import { ExternalLink, FileText, FlaskConical, Loader2, Sparkles, Upload } from 'lucide-react';
import { motion } from 'framer-motion';
import SuccessModal from './ui/SuccessModal';
import GlassCard from './ui/GlassCard';
import { useMyLab } from '../hooks/useMyLab';
import { Badge } from './ui/Badge';
import { Button } from './ui/Button';

const MotionDiv = motion.div;

export default function MyLab() {
    const { papers, isLoading, mintingIds, isSuccessModalOpen, mintResult, mintNFT, closeSuccessModal, t } = useMyLab();

    if (isLoading) {
        return (
            <div className="glass-card flex min-h-[50vh] items-center justify-center p-8">
                <div className="text-center">
                    <Loader2 className="mx-auto mb-4 h-12 w-12 animate-spin text-primary" />
                    <p className="text-sm text-ink-muted">{t('myLab.loading')}</p>
                </div>
            </div>
        );
    }

    return (
        <MotionDiv initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
            <div className="glass-card p-7">
                <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
                    <div>
                        <p className="clay-chip mb-4">{t('layout.workspace')}</p>
                        <h1 className="flex items-center gap-3 font-display text-4xl font-semibold text-ink">
                            <FlaskConical className="h-8 w-8 text-primary" />
                            {t('myLab.title')}
                        </h1>
                        <p className="mt-3 text-sm leading-7 text-ink-muted">{t('myLab.subtitle')}</p>
                    </div>
                    <Link to="/upload" className="clay-button clay-button-primary justify-center text-white">
                        <Upload className="h-4 w-4" />
                        {papers.length ? t('myLab.uploadAnother') : t('myLab.uploadCta')}
                    </Link>
                </div>
            </div>

            <SuccessModal
                isOpen={isSuccessModalOpen}
                onClose={closeSuccessModal}
                title={mintResult.title}
                message={mintResult.message}
                txHash={mintResult.txHash}
            />

            {papers.length === 0 ? (
                <GlassCard className="p-10 text-center">
                    <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-white text-primary shadow-clay-soft">
                        <FileText className="h-10 w-10" />
                    </div>
                    <h3 className="font-display text-3xl font-semibold text-ink">{t('myLab.emptyTitle')}</h3>
                    <p className="mx-auto mt-3 max-w-lg text-sm leading-7 text-ink-muted">{t('myLab.emptyDescription')}</p>
                    <Link to="/upload" className="clay-button clay-button-primary mt-6 inline-flex text-white">
                        <Upload className="h-4 w-4" />
                        {t('myLab.uploadCta')}
                    </Link>
                </GlassCard>
            ) : (
                <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
                    {papers.map((paper, index) => (
                        <GlassCard key={paper.id} delay={index * 0.06} hoverEffect className="flex flex-col p-6">
                            <div className="mb-4 flex items-start justify-between gap-3">
                                <Badge variant={paper.nft_minted ? 'success' : 'default'}>
                                    {paper.nft_minted ? t('myLab.minted') : (paper.type || t('myLab.paperFallback'))}
                                </Badge>
                                <span className="text-xs text-ink-soft">{paper.created_at ? new Date(paper.created_at).toLocaleDateString() : t('myLab.unknownDate')}</span>
                            </div>

                            <h3 className="line-clamp-2 font-display text-2xl font-semibold text-ink">{paper.title}</h3>
                            <p className="mt-3 line-clamp-3 flex-1 text-sm leading-7 text-ink-muted">{paper.abstract || t('myLab.noAbstract')}</p>

                            <div className="mt-5 flex items-center justify-between gap-3 border-t border-white/60 pt-4">
                                {paper.ipfs_url ? (
                                    <a href={paper.ipfs_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 text-sm font-semibold text-ink hover:text-primary">
                                        <ExternalLink className="h-4 w-4" />
                                        {t('myLab.ipfs')}
                                    </a>
                                ) : (
                                    <span className="text-sm text-ink-soft">{t('myLab.ipfs')}</span>
                                )}
                                <Button
                                    onClick={() => mintNFT(paper)}
                                    disabled={paper.nft_minted || mintingIds[paper.id]}
                                    size="sm"
                                    className="justify-center text-white"
                                >
                                    {mintingIds[paper.id]
                                        ? <><Loader2 className="h-4 w-4 animate-spin" />{t('myLab.minting')}</>
                                        : <><Sparkles className="h-4 w-4" />{t('myLab.mintAction')}</>}
                                </Button>
                            </div>
                        </GlassCard>
                    ))}
                </div>
            )}
        </MotionDiv>
    );
}
