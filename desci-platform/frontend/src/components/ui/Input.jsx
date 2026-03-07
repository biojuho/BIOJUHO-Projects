import { forwardRef } from 'react';
import { cva } from 'class-variance-authority';
import { cn } from '../../lib/utils';

const inputVariants = cva(
  'flex w-full text-sm transition-all duration-300 ease-smooth file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-white/30 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50',
  {
    variants: {
      variant: {
        default:
          'h-10 rounded-md border border-input bg-transparent px-3 py-1 text-foreground shadow-sm focus-visible:ring-1 focus-visible:ring-ring',
        glass:
          'rounded-xl px-4 py-3 text-white bg-white/[0.04] border border-white/[0.08] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.02)] focus:border-primary/40 focus:bg-white/[0.06] focus:shadow-[0_0_0_3px_rgba(0,212,170,0.1),inset_0_1px_0_0_rgba(255,255,255,0.04)]',
      },
    },
    defaultVariants: {
      variant: 'glass',
    },
  }
);

const Input = forwardRef(({ className, type, variant, ...props }, ref) => {
  return (
    <input
      type={type}
      className={cn(inputVariants({ variant, className }))}
      ref={ref}
      {...props}
    />
  );
});
Input.displayName = 'Input';

// eslint-disable-next-line react-refresh/only-export-components
export { Input, inputVariants };
export default Input;
