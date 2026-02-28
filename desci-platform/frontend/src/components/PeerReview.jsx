import React, { useState } from 'react';
import { FileCheck, ShieldAlert, Award, ChevronRight, Beaker, Zap } from 'lucide-react';
import { useToast } from '../contexts/ToastContext';

// Hardcoded dummy papers for the MVP demo
const DUMMY_PAPERS = [
  { id: 1, title: 'CRISPR-Cas9 Off-target Effects in Human Cells', author: 'Dr. Sarah Chen', category: 'Genetics' },
  { id: 2, title: 'Novel mRNA Delivery Nanoparticles for Oncology', author: 'BioTech Labs', category: 'Nanotech' },
  { id: 3, title: 'AI-driven Protein Folding Prediction Models', author: 'Team AlphaBio', category: 'Computing' }
];

export default function PeerReview() {
  const [selectedPaper, setSelectedPaper] = useState(null);
  const [score, setScore] = useState(5);
  const [reviewText, setReviewText] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { showToast } = useToast();

  const handleSubmitReview = (e) => {
    e.preventDefault();
    if (!reviewText) {
      showToast('리뷰 코멘트를 작성해주세요.', 'warning');
      return;
    }

    setIsSubmitting(true);
    // TODO: Smart contract integration to mint reward DSCI tokens
    setTimeout(() => {
      setIsSubmitting(false);
      showToast('리뷰가 등록되었습니다! 보상으로 10 DSCI 토큰이 지급되었습니다.', 'success');
      setSelectedPaper(null);
      setReviewText('');
      setScore(5);
    }, 2500);
  };

  return (
    <div className="p-4 sm:p-8 max-w-7xl mx-auto animate-in fade-in duration-500 flex flex-col md:flex-row gap-8">
      
      {/* Left side: Paper Selection */}
      <div className="w-full md:w-1/3 xl:w-1/4 flex flex-col gap-6">
        <div>
           <h1 className="text-3xl font-display font-bold text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-teal-200 mb-3 flex items-center gap-3">
             <Beaker className="text-emerald-400 w-8 h-8" />
             Peer Review
           </h1>
           <p className="text-slate-400 text-sm leading-relaxed">
             동료 평가가 필요한 논문 목록입니다. 리뷰를 남기고 네트워크 기여도에 따른 <span className="text-emerald-400 font-semibold">DSCI 토큰</span>을 보상으로 받으세요.
           </p>
        </div>
        
        <div className="space-y-4">
          {DUMMY_PAPERS.map(paper => (
            <div 
              key={paper.id}
              onClick={() => setSelectedPaper(paper)}
              className={`group relative p-5 rounded-2xl border transition-all duration-300 cursor-pointer overflow-hidden ${
                selectedPaper?.id === paper.id 
                  ? 'bg-emerald-900/30 border-emerald-500/50 shadow-lg shadow-emerald-500/10' 
                  : 'bg-slate-900/40 border-slate-700/50 hover:bg-slate-800/60 hover:border-slate-600'
              }`}
            >
              <div className={`absolute top-0 right-0 w-32 h-32 bg-emerald-500/10 blur-3xl -mr-16 -mt-16 transition-opacity duration-500 ${selectedPaper?.id === paper.id ? 'opacity-100' : 'opacity-0 group-hover:opacity-50'}`} />
              
              <div className="flex justify-between items-start mb-3 relative z-10">
                <span className={`text-xs px-2.5 py-1 rounded-md font-medium tracking-wide ${selectedPaper?.id === paper.id ? 'bg-emerald-500/20 text-emerald-300' : 'bg-slate-800 text-slate-400'}`}>
                   {paper.category}
                </span>
                <ChevronRight className={`w-5 h-5 transition-transform duration-300 ${selectedPaper?.id === paper.id ? 'text-emerald-400 translate-x-1' : 'text-slate-600 group-hover:text-slate-400 group-hover:translate-x-0.5'}`} />
              </div>
              <h3 className={`font-semibold line-clamp-2 leading-snug relative z-10 ${selectedPaper?.id === paper.id ? 'text-white' : 'text-slate-300'}`}>
                 {paper.title}
              </h3>
              <p className="text-slate-500 text-sm mt-3 flex items-center gap-2 relative z-10">
                 <div className="w-5 h-5 rounded-full bg-slate-800 flex items-center justify-center text-[10px]">👨‍🔬</div>
                 {paper.author}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Right side: Review Form */}
      <div className="w-full md:w-2/3 xl:w-3/4">
        {selectedPaper ? (
          <div className="bg-slate-900/80 backdrop-blur-xl border border-white/10 rounded-3xl p-6 sm:p-10 relative overflow-hidden shadow-2xl flex flex-col h-full min-h-[600px]">
            {/* Background glowing orb */}
            <div className="absolute top-0 right-0 -mr-20 -mt-20 w-80 h-80 bg-emerald-500/10 blur-[120px] rounded-full pointer-events-none" />

            <div className="mb-10 border-b border-white/10 pb-8 relative z-10">
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm font-medium mb-4">
                 <Zap className="w-4 h-4" /> Actively Reviewing
              </div>
              <h2 className="text-3xl font-bold text-white mb-3 leading-tight">{selectedPaper.title}</h2>
              <p className="text-emerald-400/80 font-medium text-lg flex items-center gap-2">
                 <span className="w-8 h-8 rounded-full bg-emerald-900/50 flex items-center justify-center text-sm border border-emerald-500/20">👨‍🔬</span>
                 {selectedPaper.author}
              </p>
            </div>

            <form onSubmit={handleSubmitReview} className="space-y-8 flex-1 flex flex-col relative z-10">
              <div className="bg-slate-800/40 p-6 rounded-2xl border border-slate-700/50">
                <div className="flex justify-between items-center mb-4">
                   <label className="text-sm font-semibold text-slate-300 uppercase tracking-wider">연구 타당성 점수</label>
                   <span className="text-3xl font-black text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-teal-300 w-12 text-right">{score}</span>
                </div>
                <div className="relative pt-2">
                  <input 
                    type="range" 
                    min="1" max="10" 
                    value={score} 
                    onChange={(e) => setScore(e.target.value)}
                    className="w-full h-3 bg-slate-900 rounded-full appearance-none cursor-pointer border border-slate-700
                               [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-6 [&::-webkit-slider-thumb]:h-6 
                               [&::-webkit-slider-thumb]:bg-emerald-400 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:shadow-[0_0_15px_rgba(52,211,153,0.5)]"
                  />
                  <div className="flex justify-between text-xs text-slate-500 mt-3 font-medium">
                     <span>1 (Poor)</span>
                     <span>5 (Average)</span>
                     <span>10 (Excellent)</span>
                  </div>
                </div>
              </div>

              <div className="flex-1 flex flex-col">
                <label className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-3">상세 평가 의견 (Critique)</label>
                <textarea 
                  value={reviewText}
                  onChange={(e) => setReviewText(e.target.value)}
                  className="flex-1 w-full min-h-[200px] bg-slate-900/50 border border-slate-700 rounded-2xl p-5 text-slate-200 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/50 transition-all resize-none placeholder:text-slate-600 leading-relaxed font-serif" 
                  placeholder="연구 방법론의 결함, 결과의 재현성, 학문적 기여도 등에 대한 건설적인 비판을 작성해주세요..."
                />
              </div>

              <div className="bg-emerald-900/20 border border-emerald-500/30 rounded-2xl p-5 flex gap-4 items-start xl:items-center">
                <div className="bg-emerald-500/20 p-2.5 rounded-xl shrink-0">
                   <ShieldAlert className="w-6 h-6 text-emerald-400" />
                </div>
                <p className="text-sm text-emerald-100/80 leading-relaxed">
                   제출된 리뷰는 블록체인에 해시되어 영구 기록되며, 품질 검증 후 스마트 컨트랙트를 통해 기여도에 따라 
                   <strong className="text-emerald-300 font-bold mx-1 px-1.5 py-0.5 bg-emerald-500/20 rounded">10 DSCI</strong> 
                   보상이 지갑으로 자동 할당됩니다.
                </p>
              </div>

              <div className="flex justify-end pt-2">
                <button 
                  type="submit" 
                  disabled={isSubmitting}
                  className="px-8 py-4 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-white rounded-2xl font-bold flex items-center justify-center gap-3 shadow-[0_0_20px_rgba(16,185,129,0.3)] hover:shadow-[0_0_30px_rgba(16,185,129,0.5)] transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed w-full sm:w-auto min-w-[240px] group"
                >
                  {isSubmitting ? (
                    <>
                      <div className="w-5 h-5 border-3 border-white/20 border-t-white rounded-full animate-spin" />
                      컨트랙트 기록 중...
                    </>
                  ) : (
                    <>
                      <Award className="w-6 h-6 group-hover:scale-110 transition-transform" />
                      <span className="text-lg">제출 및 보상 청구</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 border-2 border-dashed border-slate-700/50 rounded-3xl min-h-[600px] bg-slate-900/20">
            <div className="w-24 h-24 rounded-full bg-slate-800/50 flex items-center justify-center mb-6">
               <FileCheck className="w-10 h-10 opacity-40" />
            </div>
            <h3 className="text-xl font-display font-medium text-slate-400 mb-2">논문을 선택해주세요</h3>
            <p className="text-sm text-slate-600">좌측 목록에서 리뷰할 문서를 클릭하면 상세 내용이 표시됩니다.</p>
          </div>
        )}
      </div>
    </div>
  );
}
