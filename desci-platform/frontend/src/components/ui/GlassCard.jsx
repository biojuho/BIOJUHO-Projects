import { motion } from 'framer-motion';
import { cn } from '../../lib/utils';

const GlassCard = ({
  children,
  className = '',
  hoverEffect = false,
  delay = 0,
  animate = true,
  padding = true,
  as = 'div',
  onClick,
  role,
  tabIndex,
  'aria-label': ariaLabel,
}) => {
  const Component = animate ? motion[as] || motion.div : as;

  const motionProps = animate ? {
    initial: { opacity: 0, y: 20 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.45, delay, ease: [0.2, 0.9, 0.2, 1] },
  } : {};

  const interactiveProps = onClick ? {
    onClick,
    role: role || 'button',
    tabIndex: tabIndex ?? 0,
    'aria-label': ariaLabel,
    onKeyDown: (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        onClick(event);
      }
    },
  } : {};

  return (
    <Component
      {...motionProps}
      {...interactiveProps}
      className={cn(
        'glass-card relative overflow-hidden',
        padding && 'p-6',
        hoverEffect && 'hover:-translate-y-1 hover:shadow-float',
        onClick && 'cursor-pointer',
        className
      )}
    >
      <div className="relative z-10">{children}</div>
    </Component>
  );
};

export default GlassCard;
