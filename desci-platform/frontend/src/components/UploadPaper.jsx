import React, { useState } from 'react';
import { Upload, FileText, CheckCircle, Loader2 } from 'lucide-react';
import { useToast } from '../contexts/ToastContext';
import api from '../services/api';

export default function UploadPaper() {
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState('');
  const [authors, setAuthors] = useState('');
  const [abstract, setAbstract] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const { showToast } = useToast();

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

    setIsUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', title);
    formData.append('abstract', abstract);
    formData.append('authors', authors);

    try {
      await api.post('/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      showToast('논문이 성공적으로 업로드되었습니다!', 'success');
      setFile(null);
      setTitle('');
      setAuthors('');
      setAbstract('');
    } catch (err) {
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

      <div className="bg-white/[0.03] backdrop-blur-xl border border-white/[0.06] rounded-2xl p-6 sm:p-8 shadow-2xl">
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
              <input 
                type="text" 
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="glass-input w-full" 
                placeholder="Ex) A novel approach to targeted CRISPR-Cas9..."
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-white/70 mb-2">저자 (Authors)</label>
              <input 
                type="text" 
                value={authors}
                onChange={(e) => setAuthors(e.target.value)}
                className="glass-input w-full" 
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

          <div className="pt-4 flex justify-end">
            <button 
              type="submit" 
              disabled={isUploading || !file}
              className="glass-button px-8 py-3 bg-primary/20 hover:bg-primary/30 text-primary-300 font-semibold flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              {isUploading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  업로드 처리 중...
                </>
              ) : (
                <>
                  <Upload className="w-4 h-4" />
                  IPFS에 분산 저장 및 논문 등록
                </>
              )}
            </button>
          </div>

        </form>
      </div>
    </div>
  );
}
