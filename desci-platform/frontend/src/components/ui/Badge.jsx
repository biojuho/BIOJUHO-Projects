/* eslint-disable react-refresh/only-export-components */
import { cva } from 'class-variance-authority';
import { cn } from '../../lib/utils';

const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-semibold tracking-[0.16em] uppercase transition-colors',
  {
    variants: {
      variant: {
        default: 'bg-primary/15 text-primary border border-primary/20',
        success: 'bg-success/15 text-success border border-success/20',
        warning: 'bg-warning/15 text-warning-dark border border-warning/20',
        error: 'bg-error/15 text-error-dark border border-error/20',
        info: 'bg-info/15 text-info-dark border border-info/20',
        accent: 'bg-highlight/18 text-highlight-dark border border-highlight/20',
        secondary: 'bg-surface/70 text-ink-muted border border-surface-line/70',
        outline: 'bg-white/55 text-ink border border-white/70',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
);

function Badge({ className, variant, ...props }) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
