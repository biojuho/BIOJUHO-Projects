
import { motion } from 'framer-motion';

const GlassCard = ({
  children,
  className = "",
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
    transition: { duration: 0.5, delay, ease: [0.16, 1, 0.3, 1] },
  } : {};

  const interactiveProps = onClick ? {
    onClick,
    role: role || 'button',
    tabIndex: tabIndex ?? 0,
    'aria-label': ariaLabel,
    onKeyDown: (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        onClick(e);
      }
    },
  } : {};

  return (
    <Component
      {...motionProps}
      {...interactiveProps}
      className={`
        relative overflow-hidden
        bg-white/[0.03] backdrop-blur-xl border border-white/[0.06]
        rounded-2xl
        ${padding ? 'p-6' : ''}
        ${hoverEffect ? 'hover:bg-white/[0.05] hover:border-white/[0.1] hover:-translate-y-1 transition-all duration-400 cursor-pointer' : ''}
        ${onClick ? 'cursor-pointer focus-visible:ring-2 focus-visible:ring-primary/50 focus-visible:ring-offset-2 focus-visible:ring-offset-[#040811] focus-visible:outline-none' : ''}
        ${className}
      `.trim().replace(/\s+/g, ' ')}
      style={{
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 0 rgba(255, 255, 255, 0.03)',
      }}
    >
      {/* Subtle top gradient highlight */}
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/[0.08] to-transparent pointer-events-none" aria-hidden="true" />

      {/* Content */}
      <div className="relative z-10">
        {children}
      </div>
    </Component>
  );
};

export default GlassCard;
