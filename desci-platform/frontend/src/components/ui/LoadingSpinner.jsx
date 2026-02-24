/**
 * LoadingSpinner Component
 * Consistent loading indicator across the app
 */
import { Loader2 } from 'lucide-react';

const LoadingSpinner = ({
  size = 'md',
  label = 'Loading...',
  showLabel = true,
  className = '',
  fullScreen = false,
}) => {
  const sizes = {
    sm: { icon: 24, text: 'text-sm' },
    md: { icon: 40, text: 'text-base' },
    lg: { icon: 56, text: 'text-lg' },
    xl: { icon: 72, text: 'text-xl' },
  };

  const content = (
    <div className={`flex flex-col items-center justify-center gap-4 ${className}`}>
      <Loader2
        size={sizes[size].icon}
        className="animate-spin text-primary"
        aria-hidden="true"
      />
      {showLabel && (
        <p className={`text-gray-400 ${sizes[size].text}`} role="status" aria-live="polite">
          {label}
        </p>
      )}
    </div>
  );

  if (fullScreen) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-background/80 backdrop-blur-sm z-50">
        {content}
      </div>
    );
  }

  return content;
};

// Page-level loading state
export const PageLoading = ({ label = 'Loading...' }) => (
  <div className="flex items-center justify-center min-h-[60vh]">
    <LoadingSpinner size="lg" label={label} />
  </div>
);

// Inline loading for buttons or small areas
export const InlineLoading = ({ label = 'Loading...' }) => (
  <LoadingSpinner size="sm" label={label} showLabel={false} />
);

export default LoadingSpinner;
