import { forwardRef } from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva } from 'class-variance-authority';
import { Loader2 } from 'lucide-react';
import { cn } from '../../lib/utils';

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap font-semibold rounded-xl transition-all duration-300 ease-[cubic-bezier(.16,1,.3,1)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:opacity-40 disabled:pointer-events-none active:scale-[0.97] [&_svg]:pointer-events-none [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        default:
          'text-white bg-gradient-to-r from-primary to-primary-600 shadow-lg shadow-primary/15 hover:-translate-y-0.5 hover:shadow-xl hover:shadow-primary/25',
        secondary:
          'text-white bg-gradient-to-r from-accent to-accent-dark shadow-lg shadow-accent/15 hover:-translate-y-0.5 hover:shadow-xl hover:shadow-accent/25',
        ghost:
          'bg-white/[0.04] text-white/80 border border-white/[0.06] hover:bg-white/[0.08] hover:border-white/[0.12]',
        destructive:
          'bg-destructive/[0.08] text-red-400 border border-destructive/20 hover:bg-destructive/[0.15] hover:border-destructive/30',
        success:
          'bg-success/[0.08] text-emerald-400 border border-success/20 hover:bg-success/[0.15] hover:border-success/30',
        outline:
          'bg-transparent text-white/70 border border-white/[0.08] hover:bg-white/[0.04] hover:border-white/[0.15] hover:text-white',
        link: 'text-primary underline-offset-4 hover:underline',
      },
      size: {
        default: 'text-sm h-10 px-4 py-2.5',
        sm: 'text-sm h-8 px-3 py-1.5',
        lg: 'text-base h-12 px-6 py-3',
        xl: 'text-lg h-14 px-8 py-4',
        icon: 'h-10 w-10',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
);

const Button = forwardRef(
  (
    {
      className,
      variant,
      size,
      asChild = false,
      loading = false,
      disabled = false,
      leftIcon,
      rightIcon,
      children,
      ...props
    },
    ref
  ) => {
    if (asChild) {
      return (
        <Slot
          className={cn(buttonVariants({ variant, size, className }))}
          ref={ref}
          {...props}
        />
      );
    }

    const isDisabled = loading || disabled;

    return (
      <button
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        disabled={isDisabled}
        aria-disabled={isDisabled}
        aria-busy={loading}
        {...props}
      >
        {loading ? (
          <>
            <Loader2 className="animate-spin" aria-hidden="true" />
            <span>Loading...</span>
          </>
        ) : (
          <>
            {leftIcon && (
              <span className="flex-shrink-0" aria-hidden="true">
                {leftIcon}
              </span>
            )}
            {children}
            {rightIcon && (
              <span className="flex-shrink-0" aria-hidden="true">
                {rightIcon}
              </span>
            )}
          </>
        )}
      </button>
    );
  }
);
Button.displayName = 'Button';

export { Button, buttonVariants };
export default Button;
