import { useState } from 'react';
import client from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';
import Button from './ui/Button';
import Input from './ui/Input';
import Terms from './Terms';

export default function Upload() {
    const { walletAddress } = useAuth();
    const { showToast } = useToast();
    const [file, setFile] = useState(null);
    const [title, setTitle] = useState('');
    const [abstract, setAbstract] = useState('');
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState('');
    const [termsAccepted, setTermsAccepted] = useState(false);
    const [showTerms, setShowTerms] = useState(false);

    // 0: idle, 1: reading, 2: ipfs, 3: ai vectorizing, 4: complete
    const [uploadStep, setUploadStep] = useState(0);

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

        if (!termsAccepted) {
            setError('이용약관 및 개인정보 처리방침에 동의해주세요.');
            showToast('약관 동의가 필요합니다.', 'warning');
            return;
        }

        setLoading(true);
        setUploadStep(1);
        setError('');
        setResult(null);

        const formData = new FormData();
        formData.append('file', file);
        formData.append('title', title);
        formData.append('abstract', abstract);

        try {
            await new Promise(r => setTimeout(r, 800));
            setUploadStep(2);

            await client.post('/upload', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
            });

            setUploadStep(3);
            await new Promise(r => setTimeout(r, 1200));

            setUploadStep(4);

            try {
                if (walletAddress) {
                    await client.post(`/reward/paper?user_address=${walletAddress}`);
                    showToast('보상 토큰이 지급되었습니다! 💰', 'success');
                } else {
                    showToast("지갑이 연결되지 않았어요! 😢 보상은 다음 기회에...", 'warning');
                    console.warn("Wallet not connected, skipping reward trigger");
                }
            } catch (rewardError) {
                console.warn("Reward trigger failed", rewardError);
            }

        } catch (err) {
            console.error('Upload failed:', err);
            setError(err.response?.data?.detail || '업로드 중 오류가 발생했습니다.');
            showToast('업로드에 실패했습니다.', 'error');
        } finally {
            setLoading(false);
            if(uploadStep !== 4) setUploadStep(0);
        }
    };

    const getProgressInfo = () => {
        switch(uploadStep) {
            case 1: return { text: "문서를 읽고 파싱하는 중...", percent: 25 };
            case 2: return { text: "IPFS 분산 저장소에 업로드 중...", percent: 50 };
            case 3: return { text: "AI 벡터 DB에 논문 지식 등록 중...", percent: 85 };
            case 4: return { text: "업로드 및 분석 완료!", percent: 100 };
            default: return { text: "", percent: 0 };
        }
    };

    const progress = getProgressInfo();

    return (
        <div className="p-2 sm:p-6">
            <div className="max-w-2xl mx-auto bg-white/[0.03] backdrop-blur-xl rounded-2xl p-8 border border-white/[0.06]"
                 style={{ boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}>
                <h2 className="font-display text-2xl font-bold text-white mb-6 flex items-center gap-3">
                    📄 연구 논문 업로드
                </h2>

                <form onSubmit={handleSubmit} className="space-y-6">
                    {/* File Input */}
                    <div className="relative group cursor-pointer">
                        <div className="absolute -inset-0.5 rounded-xl opacity-60 group-hover:opacity-100 transition duration-500"
                             style={{ background: 'linear-gradient(135deg, rgba(0,212,170,0.4), rgba(99,102,241,0.4))' }} />
                        <div className="relative bg-[#040811] rounded-xl">
                            <div className="border-2 border-dashed border-white/[0.08] rounded-xl p-10 text-center hover:bg-white/[0.02] transition-all group-hover:border-white/[0.15]">
                                <input
                                    type="file"
                                    accept=".pdf"
                                    onChange={handleFileChange}
                                    className="hidden"
                                    id="file-upload"
                                />
                                <label htmlFor="file-upload" className="cursor-pointer block w-full h-full">
                                    <span className="text-5xl block mb-4 transform group-hover:scale-110 transition-transform duration-300">
                                        {file ? '📄' : '📤'}
                                    </span>
                                    <span className="text-lg font-bold text-gradient font-display">
                                        {file ? file.name : 'PDF 논문을 여기에 드롭하세요'}
                                    </span>
                                    <p className="text-white/25 text-sm mt-3 font-medium">
                                        또는 클릭하여 파일 선택 (최대 10MB)
                                    </p>
                                    <div className="mt-4 flex justify-center gap-2">
                                        <span className="badge-primary text-[10px]">IPFS 저장</span>
                                        <span className="badge-primary text-[10px]">위변조 방지</span>
                                    </div>
                                </label>
                            </div>
                        </div>
                    </div>

                    {/* Metadata Inputs */}
                    <Input
                        label="논문 제목"
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                        placeholder="논문 제목을 입력하세요"
                    />

                    <Input
                        label="초록 (Abstract)"
                        value={abstract}
                        onChange={(e) => setAbstract(e.target.value)}
                        placeholder="논문 요약을 입력하세요"
                        textarea
                        rows="4"
                    />

                    {/* Terms Agreement */}
                    <div className="flex items-center gap-3 p-4 bg-white/[0.02] rounded-xl border border-white/[0.04]">
                        <input
                            type="checkbox"
                            id="terms"
                            checked={termsAccepted}
                            onChange={(e) => setTermsAccepted(e.target.checked)}
                            className="w-5 h-5 rounded border-white/20 text-primary focus:ring-primary/50 bg-white/[0.04]"
                        />
                        <label htmlFor="terms" className="text-white/50 text-sm select-none cursor-pointer">
                            <button
                                type="button"
                                onClick={() => setShowTerms(true)}
                                className="text-primary hover:text-primary-300 underline underline-offset-2 font-semibold mr-1"
                            >
                                이용약관 및 개인정보 처리방침
                            </button>
                            에 동의하며, 저작권 보유를 확인합니다.
                        </label>
                    </div>

                    {/* Error Message */}
                    {error && (
                        <div className="bg-error/[0.08] text-error-light p-4 rounded-xl border border-error/15">
                            ⚠️ {error}
                        </div>
                    )}

                    {/* Progress Bar UI */}
                    {loading && uploadStep > 0 && uploadStep < 4 && (
                        <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-6 animate-fade-in">
                            <div className="flex justify-between items-center mb-3">
                                <span className="text-sm font-medium text-white/60">
                                    {progress.text}
                                </span>
                                <span className="text-sm font-bold text-white font-display">
                                    {progress.percent}%
                                </span>
                            </div>
                            <div className="w-full bg-white/[0.04] rounded-full h-2 overflow-hidden">
                                <div
                                    className="h-2 rounded-full transition-all duration-500 flex items-center justify-end pr-1"
                                    style={{
                                        width: `${progress.percent}%`,
                                        background: 'linear-gradient(90deg, #00d4aa, #6366f1)',
                                    }}
                                >
                                    <div className="w-1.5 h-1.5 bg-white rounded-full animate-pulse"></div>
                                </div>
                            </div>

                            <div className="flex justify-between mt-4 text-xs font-medium text-white/20">
                                <span className={uploadStep >= 1 ? "text-primary" : ""}>1. 파일 읽기</span>
                                <span className={uploadStep >= 2 ? "text-accent-light" : ""}>2. IPFS 저장</span>
                                <span className={uploadStep >= 3 ? "text-highlight" : ""}>3. AI 벡터화</span>
                            </div>
                        </div>
                    )}

                    {/* Success Message */}
                    {result && (
                        <div className="bg-success/[0.08] text-success-light p-6 rounded-xl border border-success/15">
                            <h3 className="font-display font-bold text-lg mb-2">✅ 업로드 및 분석 성공!</h3>
                            <div className="space-y-2 text-sm opacity-90 break-all">
                                <div>
                                    <p><strong>IPFS CID:</strong> <span className="font-mono bg-black/20 px-1 rounded">{result.cid}</span></p>
                                    <p><strong>Gateway:</strong> <a href={result.url} target="_blank" rel="noreferrer" className="underline hover:text-white transition-colors">{result.url}</a></p>
                                </div>
                                {result.analysis && (
                                    <div className="mt-4 pt-4 border-t border-success/20">
                                        <h4 className="font-display font-semibold text-success-light mb-2">🧬 BioLinker AI 분석 결과</h4>
                                        <p><strong>상태:</strong> {result.analysis.status} (Vector Indexed)</p>
                                        <p><strong>추출 텍스트:</strong> {result.analysis.text_length}자</p>
                                        <div className="mt-2">
                                            <strong>핵심 키워드:</strong>
                                            <div className="flex flex-wrap gap-2 mt-1">
                                                {result.analysis.keywords?.map((kw, i) => (
                                                    <span key={i} className="badge-primary text-[10px]">
                                                        #{kw}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    {result && result.cid && (
                        <div className="animate-fade-in">
                            <Button
                                type="button"
                                variant="secondary"
                                onClick={() => window.location.href = `/biolinker?paper_id=${result.cid}&paper_title=${encodeURIComponent(title)}`}
                                className="w-full"
                            >
                                <span>🚀 이 논문에 맞는 과제 찾기</span>
                            </Button>
                        </div>
                    )}

                    <Button
                        type="submit"
                        loading={loading}
                        disabled={!termsAccepted}
                        className="w-full"
                    >
                        논문 등록하기
                    </Button>
                </form>

                <Terms isOpen={showTerms} onClose={() => setShowTerms(false)} />
            </div>
        </div>
    );
}
