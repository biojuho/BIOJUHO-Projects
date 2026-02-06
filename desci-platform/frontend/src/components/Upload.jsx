/**
 * Upload Component
 * Research Paper IPFS Upload Interface
 */
import { useState } from 'react';
import client from '../api/client';
import { useAuth } from '../contexts/AuthContext';

export default function Upload() {
    const { user } = useAuth();
    const [file, setFile] = useState(null);
    const [title, setTitle] = useState('');
    const [abstract, setAbstract] = useState('');
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState('');

    const handleFileChange = (e) => {
        if (e.target.files[0]) {
            setFile(e.target.files[0]);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!file || !title) {
            setError('파일과 제목을 모두 입력해주세요.');
            return;
        }

        setLoading(true);
        setError('');
        setResult(null);

        const formData = new FormData();
        formData.append('file', file);
        formData.append('title', title);
        formData.append('abstract', abstract);

        try {
            const response = await client.post('/upload', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
            });
            setResult(response.data);

            // Also trigger reward check
            try {
                // Assuming user has a wallet address, for now using mock string if not available
                // In real app, we'd get this from Web3 context
                const mockAddress = "0x123...mock";
                await client.post(\`/reward/paper?user_address=\${mockAddress}\`);
            } catch (rewardError) {
                console.warn("Reward trigger failed", rewardError);
            }

        } catch (err) {
            console.error('Upload failed:', err);
            setError(err.response?.data?.detail || '업로드 중 오류가 발생했습니다.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-900 to-pink-800 p-8">
            <div className="max-w-2xl mx-auto bg-white/10 backdrop-blur-lg rounded-2xl p-8 border border-white/20">
                <h2 className="text-3xl font-bold text-white mb-6 flex items-center gap-3">
                    📄 연구 논문 업로드
                </h2>
                
                <form onSubmit={handleSubmit} className="space-y-6">
                    {/* File Input */}
                    <div className="border-2 border-dashed border-white/30 rounded-xl p-8 text-center hover:bg-white/5 transition-colors">
                        <input
                            type="file"
                            accept=".pdf"
                            onChange={handleFileChange}
                            className="hidden"
                            id="file-upload"
                        />
                        <label htmlFor="file-upload" className="cursor-pointer block">
                            <span className="text-4xl block mb-2">📤</span>
                            <span className="text-gray-300 font-medium">
                                {file ? file.name : 'PDF 파일을 선택하세요'}
                            </span>
                            <p className="text-gray-500 text-sm mt-2">
                                IPFS에 분산 저장됩니다 (최대 10MB)
                            </p>
                        </label>
                    </div>

                    {/* Metadata Inputs */}
                    <div>
                        <label className="block text-gray-300 mb-2">논문 제목</label>
                        <input
                            type="text"
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                            className="w-full bg-white/5 border border-white/20 rounded-lg p-3 text-white focus:ring-2 focus:ring-cyan-400 focus:outline-none"
                            placeholder="논문 제목을 입력하세요"
                        />
                    </div>

                    <div>
                        <label className="block text-gray-300 mb-2">초록 (Abstract)</label>
                        <textarea
                            value={abstract}
                            onChange={(e) => setAbstract(e.target.value)}
                            rows="4"
                            className="w-full bg-white/5 border border-white/20 rounded-lg p-3 text-white focus:ring-2 focus:ring-cyan-400 focus:outline-none"
                            placeholder="논문 요약을 입력하세요"
                        />
                    </div>

                    {/* Error Message */}
                    {error && (
                        <div className="bg-red-500/20 text-red-200 p-4 rounded-lg border border-red-500/50">
                            ⚠️ {error}
                        </div>
                    )}

                    {/* Success Message */}
                    {result && (
                        <div className="bg-green-500/20 text-green-200 p-6 rounded-lg border border-green-500/50">
                            <h3 className="font-bold text-lg mb-2">✅ 업로드 성공!</h3>
                            <div className="space-y-1 text-sm opacity-90 break-all">
                                <p><strong>IPFS CID:</strong> {result.cid}</p>
                                <p><strong>Gateway:</strong> <a href={result.url} target="_blank" rel="noreferrer" className="underline hover:text-white">{result.url}</a></p>
                                {result._mock && <p className="text-yellow-300 mt-2 text-xs">⚠️ Mock Mode: 실제 IPFS에는 저장되지 않았습니다.</p>}
                            </div>
                        </div>
                    )}

                    <button
                        type="submit"
                        disabled={loading}
                        className="w-full bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-bold py-4 rounded-xl hover:opacity-90 transition-all disabled:opacity-50"
                    >
                        {loading ? 'IPFS 업로드 및 해시 생성 중...' : '논문 등록하기'}
                    </button>
                </form>
            </div>
        </div>
    );
}
