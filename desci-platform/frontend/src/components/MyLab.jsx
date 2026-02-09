import { useState, useEffect } from 'react';
import client from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';
import { Link } from 'react-router-dom';
import { Loader2, Upload, FileText } from 'lucide-react';
import SuccessModal from './ui/SuccessModal';

export default function MyLab() {
    const { user, walletAddress } = useAuth();
    const { showToast } = useToast();
    const [papers, setPapers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [minting, setMinting] = useState({});

    // Modal State
    const [showSuccessModal, setShowSuccessModal] = useState(false);
    const [modalData, setModalData] = useState({ title: '', message: '', txHash: '' });

    useEffect(() => {
        const fetchPapers = async () => {
            try {
                const response = await client.get('/papers/me');
                setPapers(response.data);
            } catch (err) {
                console.error('Failed to fetch papers:', err);
                showToast("연구 데이터를 불러오는데 실패했습니다.", 'error');
            } finally {
                setLoading(false);
            }
        };
        fetchPapers();
    }, [showToast]);

    const mintNFT = async (paper) => {
        if (!walletAddress) {
            showToast("지갑이 연결되지 않았습니다. 😢", 'warning');
            return;
        }

        setMinting(prev => ({ ...prev, [paper.id]: true }));

        try {
            const res = await client.post('/nft/mint', {
                user_address: walletAddress,
                token_uri: paper.ipfs_url
            });

            if (res.data.success) {
                setModalData({
                    title: "NFT Minted Successfully! 💎",
                    message: `Your IP-NFT for "${paper.title}" has been minted on the blockchain.`,
                    txHash: res.data.tx_hash
                });
                setShowSuccessModal(true);
            } else {
                showToast("Minting failed: " + res.data.error, 'error');
            }
        } catch (err) {
            console.error(err);
            showToast("Minting Error", 'error');
        } finally {
            setMinting(prev => ({ ...prev, [paper.id]: false }));
        }
    };

    if (loading) {
        return (
            <div className="flex justify-center items-center h-screen bg-slate-50">
                <Loader2 className="animate-spin text-blue-500" size={48} />
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-50 p-6">
             <div className="max-w-6xl mx-auto">
                <h1 className="text-3xl font-bold mb-8 text-slate-800 flex items-center gap-2">
                  My Research Lab 🔬
                </h1>
                
                <SuccessModal 
                    isOpen={showSuccessModal} 
                    onClose={() => setShowSuccessModal(false)}
                    title={modalData.title}
                    message={modalData.message}
                    txHash={modalData.txHash}
                />

                {papers.length === 0 ? (
                    <div className="text-center py-20 bg-white rounded-3xl border-2 border-dashed border-slate-200">
                        <FileText size={64} className="mx-auto text-slate-300 mb-4" />
                        <p className="text-xl text-slate-500 mb-6">No research papers yet.</p>
                        <Link to="/upload" className="inline-flex items-center px-6 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors font-semibold">
                            <Upload size={20} className="mr-2" /> Upload Your First Paper
                        </Link>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {papers.map(paper => (
                            <div key={paper.id} className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden hover:shadow-md transition-shadow">
                                <div className="p-6">
                                    <div className="flex justify-between items-start mb-4">
                                        <span className="px-3 py-1 bg-blue-50 text-blue-600 text-xs font-bold rounded-full uppercase tracking-wide">
                                            {paper.type || "Paper"}
                                        </span>
                                        <span className="text-xs text-slate-400">
                                            {new Date(paper.created_at || Date.now()).toLocaleDateString()}
                                        </span>
                                    </div>
                                    
                                    <h3 className="text-xl font-bold text-slate-800 mb-3 line-clamp-2 min-h-[3.5rem]">
                                        {paper.title}
                                    </h3>
                                    
                                    <p className="text-slate-500 text-sm mb-6 line-clamp-3 min-h-[3.75rem]">
                                        {paper.abstract || "No abstract available."}
                                    </p>
                                    
                                    <div className="flex justify-between items-center pt-4 border-t border-slate-50">
                                        <div className="flex space-x-2">
                                        </div>
                                        
                                        <button
                                            onClick={() => mintNFT(paper)}
                                            disabled={minting[paper.id]}
                                            className={`flex items-center px-4 py-2 rounded-lg font-medium transition-all ${
                                                minting[paper.id] 
                                                    ? "bg-slate-100 text-slate-400 cursor-not-allowed"
                                                    : "bg-gradient-to-r from-indigo-500 to-purple-600 text-white shadow-lg hover:shadow-indigo-500/30 hover:-translate-y-0.5"
                                            }`}
                                        >
                                            {minting[paper.id] ? (
                                                <>
                                                    <Loader2 size={18} className="animate-spin mr-2" />
                                                    Minting...
                                                </>
                                            ) : (
                                                <>
                                                    <span className="mr-2">💎</span> Mint IP-NFT
                                                </>
                                            )}
                                        </button>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
