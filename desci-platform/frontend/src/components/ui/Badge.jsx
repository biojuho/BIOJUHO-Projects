import { cva } from 'class-variance-authority';
import { cn } from '../../lib/utils';

const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-full text-xs font-medium tracking-wide transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
  {
    variants: {
      variant: {
        default: 'px-2.5 py-0.5 text-primary bg-primary/12 border border-primary/20',
        success: 'px-2.5 py-0.5 text-emerald-400 bg-emerald-500/12 border border-emerald-500/20',
        warning: 'px-2.5 py-0.5 text-amber-400 bg-amber-500/12 border border-amber-500/20',
        error: 'px-2.5 py-0.5 text-red-400 bg-red-500/12 border border-red-500/20',
        info: 'px-2.5 py-0.5 text-blue-400 bg-blue-500/12 border border-blue-500/20',
        accent: 'px-2.5 py-0.5 text-accent-light bg-accent/12 border border-accent/20',
        secondary: 'px-2.5 py-0.5 border-transparent bg-secondary text-secondary-foreground',
        outline: 'px-2.5 py-0.5 text-foreground border border-white/[0.08]',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
);

function Badge({ className, variant, ...props }) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
