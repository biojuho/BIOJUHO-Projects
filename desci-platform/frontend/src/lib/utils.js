import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Merge Tailwind CSS classes with clsx + tailwind-merge
 * shadcn/ui standard utility
 */
export function cn(...inputs) {
  return twMerge(clsx(inputs));
}
