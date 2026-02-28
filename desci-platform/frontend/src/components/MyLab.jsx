import { Link } from 'react-router-dom';
import { Loader2, Upload, FileText, FlaskConical, ExternalLink, Sparkles } from 'lucide-react';
import { motion } from 'framer-motion';
import SuccessModal from './ui/SuccessModal';
import GlassCard from './ui/GlassCard';
import { useMyLab } from '../hooks/useMyLab';

const containerVariants = {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { staggerChildren: 0.1 } },
};

const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0 },
};

const MotionDiv = motion.div;

export default function MyLab() {
    const { papers, isLoading, mintingIds, isSuccessModalOpen, mintResult, mintNFT, closeSuccessModal } = useMyLab();

    if (isLoading) {
        return (
            <div className="flex justify-center items-center min-h-[60vh]">
                <div className="flex flex-col items-center gap-4">
                    <Loader2 className="animate-spin text-primary" size={48} />
                    <p className="text-gray-400 text-sm">Loading your research...</p>
                </div>
            </div>
        );
    }

    return (
        <MotionDiv className="space-y-8" variants={containerVariants} initial="hidden" animate="show">
            {/* Header */}
            <MotionDiv variants={itemVariants} className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-4xl font-bold text-white tracking-tight flex items-center gap-3">
                        <FlaskConical className="w-10 h-10 text-primary" />
                        My Research Lab
                    </h1>
                    <p className="text-gray-400 mt-2">Manage your research papers and mint IP-NFTs</p>
                </div>
                <Link
                    to="/upload"
                    className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-cyan-500 to-blue-600 text-white rounded-xl hover:opacity-90 transition-all shadow-lg shadow-cyan-500/20 font-medium"
                >
                    <Upload size={18} /> Upload Paper
                </Link>
            </MotionDiv>

            <SuccessModal
                isOpen={isSuccessModalOpen}
                onClose={closeSuccessModal}
                title={mintResult.title}
                message={mintResult.message}
                txHash={mintResult.txHash}
            />

            {papers.length === 0 ? (
                <MotionDiv variants={itemVariants}>
                    <GlassCard className="text-center py-16 px-8">
                        <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-white/5 flex items-center justify-center">
                            <FileText size={40} className="text-gray-500" />
                        </div>
                        <h3 className="text-2xl font-bold text-white mb-3">No Research Papers Yet</h3>
                        <p className="text-gray-400 mb-8 max-w-md mx-auto">
                            Start your DeSci journey by uploading your first research paper and mint it as an IP-NFT.
                        </p>
                        <Link
                            to="/upload"
                            className="inline-flex items-center gap-2 px-8 py-4 bg-gradient-to-r from-cyan-500 to-blue-600 text-white rounded-xl hover:opacity-90 transition-all shadow-lg shadow-cyan-500/20 font-semibold"
                        >
                            <Upload size={20} /> Upload Your First Paper
                        </Link>
                    </GlassCard>
                </MotionDiv>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {papers.map((paper, index) => (
                        <GlassCard key={paper.id} delay={index * 0.1} hoverEffect={true} className="flex flex-col">
                            <div className="flex justify-between items-start mb-4">
                                <span className="px-3 py-1 bg-primary/20 text-primary text-xs font-bold rounded-full uppercase tracking-wide">
                                    {paper.type || "Paper"}
                                </span>
                                <span className="text-xs text-gray-500">
                                    {paper.created_at ? new Date(paper.created_at).toLocaleDateString() : "Unknown date"}
                                </span>
                            </div>

                            <h3 className="text-lg font-bold text-white mb-3 line-clamp-2 min-h-[3rem]">
                                {paper.title}
                            </h3>
                            <p className="text-gray-400 text-sm mb-6 line-clamp-3 flex-1">
                                {paper.abstract || "No abstract available."}
                            </p>

                            <div className="flex items-center justify-between pt-4 border-t border-white/10 mt-auto">
                                {paper.ipfs_url && (
                                    <a
                                        href={paper.ipfs_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-sm text-gray-400 hover:text-white flex items-center gap-1 transition-colors"
                                        aria-label="View on IPFS"
                                    >
                                        <ExternalLink size={14} /> IPFS
                                    </a>
                                )}
                                <button
                                    onClick={() => mintNFT(paper)}
                                    disabled={mintingIds[paper.id]}
                                    aria-label={mintingIds[paper.id] ? "Minting in progress" : "Mint IP-NFT"}
                                    className={`flex items-center gap-2 px-4 py-2 rounded-xl font-medium transition-all text-sm ${
                                        mintingIds[paper.id]
                                            ? "bg-white/5 text-gray-500 cursor-not-allowed"
                                            : "bg-gradient-to-r from-purple-500 to-pink-600 text-white shadow-lg shadow-purple-500/20 hover:-translate-y-0.5 hover:shadow-xl"
                                    }`}
                                >
                                    {mintingIds[paper.id] ? (
                                        <><Loader2 size={16} className="animate-spin" /> Minting...</>
                                    ) : (
                                        <><Sparkles size={16} /> Mint IP-NFT</>
                                    )}
                                </button>
                            </div>
                        </GlassCard>
                    ))}
                </div>
            )}
        </MotionDiv>
    );
}
