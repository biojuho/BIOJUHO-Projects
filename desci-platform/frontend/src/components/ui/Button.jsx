import { forwardRef } from 'react';
import { Loader2 } from 'lucide-react';

const Button = forwardRef(({
    children,
    variant = 'primary',
    size = 'md',
    loading = false,
    disabled = false,
    leftIcon,
    rightIcon,
    className = '',
    fullWidth = false,
    ...props
}, ref) => {
    const baseStyle = `
        inline-flex items-center justify-center gap-2
        font-semibold rounded-xl
        transition-all duration-300 ease-[cubic-bezier(.16,1,.3,1)]
        disabled:opacity-40 disabled:cursor-not-allowed
        active:scale-[0.97] transform
        focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-[#040811]
    `;

    const variants = {
        primary: `
            text-white
            bg-gradient-to-r from-primary to-primary-600
            shadow-lg shadow-primary/15
            hover:-translate-y-0.5 hover:shadow-xl hover:shadow-primary/25
            focus-visible:ring-primary/50
        `,
        secondary: `
            text-white
            bg-gradient-to-r from-accent to-accent-dark
            shadow-lg shadow-accent/15
            hover:-translate-y-0.5 hover:shadow-xl hover:shadow-accent/25
            focus-visible:ring-accent/50
        `,
        ghost: `
            bg-white/[0.04] text-white/80
            hover:bg-white/[0.08] border border-white/[0.06] hover:border-white/[0.12]
            focus-visible:ring-white/30
        `,
        danger: `
            bg-error/[0.08] text-error-light border border-error/20
            hover:bg-error/[0.15] hover:border-error/30
            focus-visible:ring-error/50
        `,
        success: `
            bg-success/[0.08] text-success-light border border-success/20
            hover:bg-success/[0.15] hover:border-success/30
            focus-visible:ring-success/50
        `,
        outline: `
            bg-transparent text-white/70 border border-white/[0.08]
            hover:bg-white/[0.04] hover:border-white/[0.15] hover:text-white
            focus-visible:ring-white/30
        `,
    };

    const sizes = {
        sm: 'text-sm px-3 py-1.5 min-h-[32px]',
        md: 'text-sm px-4 py-2.5 min-h-[40px]',
        lg: 'text-base px-6 py-3 min-h-[48px]',
        xl: 'text-lg px-8 py-4 min-h-[56px]',
    };

    const iconSizes = {
        sm: 14,
        md: 16,
        lg: 18,
        xl: 20,
    };

    const isDisabled = loading || disabled;

    return (
        <button
            ref={ref}
            className={`
                ${baseStyle}
                ${variants[variant]}
                ${sizes[size]}
                ${fullWidth ? 'w-full' : ''}
                ${className}
            `.trim().replace(/\s+/g, ' ')}
            disabled={isDisabled}
            aria-disabled={isDisabled}
            aria-busy={loading}
            {...props}
        >
            {loading ? (
                <>
                    <Loader2
                        size={iconSizes[size]}
                        className="animate-spin"
                        aria-hidden="true"
                    />
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
});

Button.displayName = 'Button';

export default Button;
