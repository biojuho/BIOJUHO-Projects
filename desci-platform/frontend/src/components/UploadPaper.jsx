import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, FileText, CheckCircle, Loader2 } from 'lucide-react';
import { useToast } from '../contexts/ToastContext';
import { useAuth } from '../contexts/AuthContext';
import api from '../services/api';
import { Card, CardContent } from './ui/Card';
import { Button } from './ui/Button';
import { Input } from './ui/Input';
import { Badge } from './ui/Badge';

export default function UploadPaper() {
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState('');
  const [authors, setAuthors] = useState('');
  const [abstract, setAbstract] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [uploadStatusText, setUploadStatusText] = useState('업로드 처리 중...');
  const [termsAgreed, setTermsAgreed] = useState(false);
  const abortControllerRef = useRef(null);
  const { showToast } = useToast();
  const { walletAddress } = useAuth();

  useEffect(() => {
    // Cleanup function to abort any pending requests when component unmounts
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file || !title || !authors) {
      showToast('필수 항목을 모두 입력해주세요.', 'warning');
      return;
    }
    if (!termsAgreed) {
      showToast('저작권 및 오픈액세스 정책에 동의해주세요.', 'warning');
      return;
    }

    setIsUploading(true);
    setUploadStatusText('IPFS 분산 저장소에 논문 업로드 중...');
    abortControllerRef.current = new AbortController();
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', title);
    formData.append('abstract', abstract);
    formData.append('authors', authors);

    try {
      const response = await api.post('/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        signal: abortControllerRef.current.signal
      });
      const result = response.data;
      
      let rewardMessage = '';
      if (walletAddress && result.cid) {
        try {
          // Legal Consent Hashing: create immutable audit trail
          const consentTimestamp = new Date().toISOString();
          const consentPayload = `consent:${consentTimestamp}|wallet:${walletAddress}|cid:${result.cid}|terms:CC-BY-4.0`;
          const encoder = new TextEncoder();
          const hashBuffer = await crypto.subtle.digest('SHA-256', encoder.encode(consentPayload));
          const consentHash = '0x' + Array.from(new Uint8Array(hashBuffer)).map(b => b.toString(16).padStart(2, '0')).join('');

          setUploadStatusText('Research Paper IP-NFT 스마트 컨트랙트 민팅 중...');
          await api.post('/nft/mint', {
            user_address: walletAddress,
            token_uri: `ipfs://${result.cid}`,
            consent_hash: consentHash,
            consent_timestamp: consentTimestamp,
          });
          
          setUploadStatusText('DeSci 보상 토큰(DSCI) 스마트 컨트랙트 분배 중...');
          await api.post(`/reward/paper?user_address=${walletAddress}`);
          
          rewardMessage = ' 분산 저장, NFT 민팅 및 보상 지급이 완료되었습니다! 💰';
        } catch (web3Err) {
          console.warn('Web3 Transaction failed:', web3Err);
          rewardMessage = ' 지갑 연동에 오류가 있어 Web3 보상 트랜잭션(NFT/DSCI) 처리에 실패하거나 지연되었습니다.';
        }
      } else if (!walletAddress) {
          rewardMessage = ' (지갑 미연결로 보상 획득 생략)';
      }

      showToast(`논문이 성공적으로 업로드되었습니다!${rewardMessage}`, 'success');
      setFile(null);
      setTitle('');
      setAuthors('');
      setAbstract('');
      setTermsAgreed(false);
    } catch (err) {
      if (err.name === 'CanceledError' || err.code === 'ERR_CANCELED') {
        console.log('Upload request was cancelled (component unmounted).');
        return;
      }
      console.error('Upload failed:', err);
      showToast(err.response?.data?.detail || '업로드 중 오류가 발생했습니다.', 'error');
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
          Research Upload
        </h1>
        <p className="text-white/40 mt-2 ml-14">새로운 연구 논문을 DeSci 생태계에 등록하고 기여도를 증명하세요.</p>
      </div>

      <Card glass className="shadow-2xl">
        <CardContent className="p-6 sm:p-8">
        <form onSubmit={handleUpload} className="space-y-6">
          
          {/* File Dropzone */}
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
                <p className="text-white/60 font-medium">여기를 클릭하거나 PDF 파일을 드래그하여 업로드하세요</p>
                <p className="text-white/30 text-sm">최대 50MB, PDF 형식만 지원</p>
              </div>
            )}
          </div>

          {/* Metadata Fields */}
          <div className="grid gap-6">
            <div>
              <label className="block text-sm font-medium text-white/70 mb-2">논문 제목 (Title)</label>
              <Input 
                type="text" 
                variant="glass"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Ex) A novel approach to targeted CRISPR-Cas9..."
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-white/70 mb-2">저자 (Authors)</label>
              <Input 
                type="text" 
                variant="glass"
                value={authors}
                onChange={(e) => setAuthors(e.target.value)}
                placeholder="Ex) John Doe, Jane Smith (쉼표로 구분)"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-white/70 mb-2">초록 (Abstract)</label>
              <textarea 
                value={abstract}
                onChange={(e) => setAbstract(e.target.value)}
                className="glass-input w-full h-32 resize-none" 
                placeholder="논문의 주요 연구 내용과 결론을 요약해주세요..."
              />
            </div>
          </div>

          {/* Legal/Compliance Agreement */}
          <div className="flex items-start gap-3 p-4 bg-primary/5 border border-primary/20 rounded-xl">
            <div className="flex-shrink-0 mt-0.5">
              <input 
                type="checkbox" 
                id="terms"
                checked={termsAgreed}
                onChange={(e) => setTermsAgreed(e.target.checked)}
                className="w-5 h-5 rounded border-white/20 bg-black/20 text-primary-500 focus:ring-primary-500/50"
              />
            </div>
            <div>
              <label htmlFor="terms" className="text-sm font-medium text-white/90 block cursor-pointer">
                [필수] 크리에이티브 커먼즈 (CC) 라이선스 및 오픈액세스 동의
              </label>
              <p className="text-xs text-white/50 mt-1">
                본 논문을 DeSci 네트워크에 업로드함으로써, 귀하는 해당 저작물이 탈중앙화 저장소(IPFS)에 영구적으로 보존되며 누구나 접근할 수 있는 오픈액세스(Open Access) 정책에 동의하는 것으로 간주됩니다.
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
                    <span>IPFS에 분산 저장 및 논문 등록</span>
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
