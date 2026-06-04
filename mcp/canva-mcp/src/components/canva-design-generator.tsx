import React, { useState, useRef } from 'react';
import { useWidgetProps, useDisplayMode } from '../hooks';
import '../styles/index.css';
import { cn } from '../lib/utils';

interface Candidate {
  id: string;
  thumbnail_url?: string;
  preview_url?: string;
  url?: string;
}

interface Props extends Record<string, unknown> {
  candidates?: Candidate[];
  job_id?: string | null;
}

const FALLBACK_DESIGN =
  `data:image/svg+xml;utf8,${encodeURIComponent(`
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 192 192">
      <rect width="192" height="192" rx="24" fill="#f3f4f6" />
      <rect x="28" y="34" width="136" height="124" rx="16" fill="#ffffff" />
      <rect x="46" y="58" width="66" height="12" rx="6" fill="#7d2ae8" opacity="0.8" />
      <rect x="46" y="88" width="100" height="10" rx="5" fill="#9ca3af" />
      <rect x="46" y="112" width="78" height="10" rx="5" fill="#d1d5db" />
      <circle cx="136" cy="62" r="18" fill="#00c4cc" opacity="0.75" />
    </svg>
  `)}`;

const CanvaDesignGenerator: React.FC = () => {
  const props = useWidgetProps<Props>({
    candidates: [],
    job_id: null
  });

  const { candidates, job_id } = props;
  const displayMode = useDisplayMode();
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const handleSelect = (candidate: Candidate) => {
    setSelectedCandidateId(candidate.id);

    if (window.parent && window.parent.postMessage) {
      window.parent.postMessage({
        type: 'canva-create-from-candidate',
        data: {
          jobId: job_id,
          candidateId: candidate.id,
          candidate
        }
      }, '*');
    }
  };

  const handleCandidateKeyDown = (
    event: React.KeyboardEvent<HTMLDivElement>,
    candidate: Candidate
  ) => {
    if (event.key === 'Enter' || event.key === ' ' || event.key === 'Spacebar') {
      event.preventDefault();
      handleSelect(candidate);
    }
  };

  const scroll = (direction: 'left' | 'right') => {
    if (scrollContainerRef.current) {
      const scrollAmount = 200;
      scrollContainerRef.current.scrollBy({
        left: direction === 'left' ? -scrollAmount : scrollAmount,
        behavior: 'smooth'
      });
    }
  };

  if (!candidates || candidates.length === 0) {
    return (
      <div className="h-[192px] rounded-xl flex items-center justify-center">
        <div className="text-center text-gray-500">
          <div className="text-4xl mb-2">🎨</div>
          <div className="text-sm font-medium">No design candidates</div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-[192px] rounded-xl relative">
      {/* Left scroll button */}
      <button
        type="button"
        aria-label="Scroll design candidates left"
        onClick={() => scroll('left')}
        className={cn(
          "absolute left-2 top-1/2 -translate-y-1/2 z-10",
          "w-8 h-8 rounded-full bg-white/90 backdrop-blur-sm",
          "flex items-center justify-center shadow-lg",
          "hover:bg-white transition-all duration-200",
          "border border-gray-200"
        )}
      >
        <svg className="w-5 h-5 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
      </button>

      {/* Carousel container */}
      <div
        ref={scrollContainerRef}
        className="h-full overflow-x-auto overflow-y-hidden flex items-center gap-3 px-12 scrollbar-hide"
        style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
      >
        {candidates.map((candidate, index) => {
          const isSelected = selectedCandidateId === candidate.id;

          return (
            <div
              key={candidate.id}
              role="button"
              tabIndex={0}
              aria-label={`Select design candidate ${index + 1}`}
              onClick={() => handleSelect(candidate)}
              onKeyDown={(event) => handleCandidateKeyDown(event, candidate)}
              className={cn(
                "relative flex-shrink-0 w-[192px] h-[192px] rounded-3xl overflow-hidden",
                "cursor-pointer",
                "bg-white border-2",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-500 focus-visible:ring-offset-2",
                isSelected ? "border-purple-500 shadow-lg" : "border-transparent"
              )}
            >
              <img
                src={candidate.thumbnail_url || candidate.preview_url || FALLBACK_DESIGN}
                alt={`Design ${index + 1}`}
                className="w-full h-full object-cover"
                loading="lazy"
              />
              {isSelected && (
                <div className="absolute top-2 right-2 w-6 h-6 bg-purple-500 rounded-full flex items-center justify-center">
                  <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Right scroll button */}
      <button
        type="button"
        aria-label="Scroll design candidates right"
        onClick={() => scroll('right')}
        className={cn(
          "absolute right-2 top-1/2 -translate-y-1/2 z-10",
          "w-8 h-8 rounded-full bg-white/90 backdrop-blur-sm",
          "flex items-center justify-center shadow-lg",
          "hover:bg-white transition-all duration-200",
          "border border-gray-200"
        )}
      >
        <svg className="w-5 h-5 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </button>

      <style>{`
        .scrollbar-hide::-webkit-scrollbar {
          display: none;
        }
      `}</style>
    </div>
  );
};

export default CanvaDesignGenerator;
