import { forwardRef, useState, useId } from 'react';
import { AlertCircle, Eye, EyeOff } from 'lucide-react';

const Input = forwardRef(({
    label,
    error,
    helperText,
    type = 'text',
    className = '',
    textarea = false,
    leftIcon,
    rightIcon,
    size = 'md',
    required = false,
    disabled = false,
    id,
    ...props
}, ref) => {
    const [showPassword, setShowPassword] = useState(false);
    const isPassword = type === 'password';
    const generatedId = useId();
    const inputId = id || generatedId;
    const errorId = `${inputId}-error`;
    const helperId = `${inputId}-helper`;

    const Component = textarea ? 'textarea' : 'input';

    const sizes = {
        sm: 'px-3 py-2 text-sm',
        md: 'px-4 py-3 text-base',
        lg: 'px-5 py-4 text-lg',
    };

    const inputStyles = `
        w-full bg-white/5 border rounded-xl text-white
        placeholder-white/40
        transition-all duration-200
        focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50
        disabled:opacity-50 disabled:cursor-not-allowed
        ${error ? 'border-error/50 focus:ring-error/50 focus:border-error/50' : 'border-white/20 hover:border-white/30'}
        ${leftIcon ? 'pl-11' : ''}
        ${rightIcon || isPassword ? 'pr-11' : ''}
        ${sizes[size]}
    `.trim().replace(/\s+/g, ' ');

    return (
        <div className={`space-y-2 ${className}`}>
            {label && (
                <label
                    htmlFor={inputId}
                    className="flex items-center gap-1 text-sm font-medium text-gray-300"
                >
                    {label}
                    {required && (
                        <span className="text-error" aria-hidden="true">*</span>
                    )}
                </label>
            )}

            <div className="relative">
                {leftIcon && (
                    <div className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none">
                        {leftIcon}
                    </div>
                )}

                <Component
                    ref={ref}
                    id={inputId}
                    type={isPassword && showPassword ? 'text' : type}
                    disabled={disabled}
                    className={inputStyles}
                    aria-invalid={!!error}
                    aria-describedby={error ? errorId : helperText ? helperId : undefined}
                    aria-required={required}
                    {...props}
                />

                {isPassword && (
                    <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white transition-colors"
                        aria-label={showPassword ? 'Hide password' : 'Show password'}
                    >
                        {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                )}

                {rightIcon && !isPassword && (
                    <div className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none">
                        {rightIcon}
                    </div>
                )}
            </div>

            {error && (
                <p
                    id={errorId}
                    role="alert"
                    className="flex items-center gap-1.5 text-sm text-error-light"
                >
                    <AlertCircle size={14} className="flex-shrink-0" aria-hidden="true" />
                    {error}
                </p>
            )}

            {helperText && !error && (
                <p
                    id={helperId}
                    className="text-sm text-gray-500"
                >
                    {helperText}
                </p>
            )}
        </div>
    );
});

Input.displayName = 'Input';

export default Input;
