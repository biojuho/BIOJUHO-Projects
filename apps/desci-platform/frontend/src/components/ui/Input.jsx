/* eslint-disable react-refresh/only-export-components */
import { forwardRef } from 'react';
import { cva } from 'class-variance-authority';
import { cn } from '../../lib/utils';

const inputVariants = cva(
  'flex w-full text-sm transition-all duration-300 ease-smooth file:border-0 file:bg-transparent file:text-sm file:font-medium focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50',
  {
    variants: {
      variant: {
        default: 'clay-input',
        glass: 'clay-input',
      },
    },
    defaultVariants: {
      variant: 'glass',
    },
  }
);

const Input = forwardRef(({ className, type, variant, ...props }, ref) => (
  <input
    type={type}
    className={cn(inputVariants({ variant, className }))}
    ref={ref}
    {...props}
  />
));

Input.displayName = 'Input';

export { Input, inputVariants };
export default Input;
