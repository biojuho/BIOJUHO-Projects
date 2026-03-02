/**
 * EmptyState Component
 * Reusable empty state with icon, title, description, and action
 */
import { motion } from 'framer-motion';
import { FileX, Search, Inbox, AlertCircle, Plus } from 'lucide-react';

const MotionDiv = motion.div;
import GlassCard from './GlassCard';
import Button from './Button';

const presetIcons = {
  empty: Inbox,
  search: Search,
  error: AlertCircle,
  file: FileX,
  default: Inbox,
};

const EmptyState = ({
  icon: CustomIcon,
  preset = 'default',
  title = 'No data found',
  description,
  action,
  actionLabel,
  onAction,
  secondaryAction,
  secondaryActionLabel,
  onSecondaryAction,
  className = '',
  compact = false,
}) => {
  const Icon = CustomIcon || presetIcons[preset] || presetIcons.default;

  return (
    <GlassCard className={`text-center ${compact ? 'py-8 px-6' : 'py-16 px-8'} ${className}`}>
      <MotionDiv
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.3 }}
      >
        {/* Icon */}
        <div className={`
          mx-auto mb-6 rounded-2xl bg-white/5 flex items-center justify-center
          ${compact ? 'w-14 h-14' : 'w-20 h-20'}
        `}>
          <Icon
            className={`text-gray-500 ${compact ? 'w-7 h-7' : 'w-10 h-10'}`}
            aria-hidden="true"
          />
        </div>

        {/* Title */}
        <h3 className={`font-bold text-white mb-2 ${compact ? 'text-lg' : 'text-2xl'}`}>
          {title}
        </h3>

        {/* Description */}
        {description && (
          <p className={`text-gray-400 mb-6 max-w-md mx-auto ${compact ? 'text-sm' : ''}`}>
            {description}
          </p>
        )}

        {/* Actions */}
        {(action || onAction) && (
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
            <Button
              onClick={onAction}
              size={compact ? 'md' : 'lg'}
              leftIcon={<Plus size={compact ? 16 : 18} />}
            >
              {actionLabel || action || 'Add New'}
            </Button>

            {(secondaryAction || onSecondaryAction) && (
              <Button
                variant="ghost"
                onClick={onSecondaryAction}
                size={compact ? 'md' : 'lg'}
              >
                {secondaryActionLabel || secondaryAction || 'Learn More'}
              </Button>
            )}
          </div>
        )}
      </MotionDiv>
    </GlassCard>
  );
};

// Preset empty states
export const NoResultsState = (props) => (
  <EmptyState
    preset="search"
    title="No results found"
    description="Try adjusting your search or filter to find what you're looking for."
    {...props}
  />
);

export const ErrorState = (props) => (
  <EmptyState
    preset="error"
    title="Something went wrong"
    description="We couldn't load the data. Please try again."
    actionLabel="Retry"
    {...props}
  />
);

export const NoDataState = (props) => (
  <EmptyState
    preset="empty"
    title="No data yet"
    description="Get started by adding your first item."
    {...props}
  />
);

export default EmptyState;
