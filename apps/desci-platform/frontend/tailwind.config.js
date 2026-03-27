/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
          100: '#dff8ef',
          200: '#b7edd8',
          300: '#92dfc2',
          400: '#69c9ad',
          500: '#46ad92',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
          light: '#8fb2ff',
          dark: '#6584d3',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        surface: {
          DEFAULT: '#efe6da',
          raised: '#f7f0e8',
          overlay: '#fffaf4',
          line: '#d7cab9',
        },
        highlight: {
          DEFAULT: '#ffb38a',
          light: '#ffd2ba',
          dark: '#ec9972',
        },
        success: {
          DEFAULT: '#5bb89e',
          light: '#84cfba',
          dark: '#42917c',
        },
        warning: {
          DEFAULT: '#e0a35a',
          light: '#edc17d',
          dark: '#c28541',
        },
        error: {
          DEFAULT: '#df7a6b',
          light: '#f4a396',
          dark: '#bf5e53',
        },
        info: {
          DEFAULT: '#7ea6ff',
          light: '#adc7ff',
          dark: '#5e84da',
        },
        ink: {
          DEFAULT: '#2f3443',
          muted: '#5c6172',
          soft: '#7f8291',
        },
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 4px)',
        sm: 'calc(var(--radius) - 8px)',
        xl: '1.75rem',
        '2xl': '2rem',
        '3xl': '2.25rem',
        '4xl': '2.75rem',
      },
      transitionTimingFunction: {
        smooth: 'cubic-bezier(.2,.9,.2,1)',
      },
      fontFamily: {
        display: ['Fraunces', 'Georgia', 'serif'],
        sans: ['Manrope', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        clay: '14px 14px 30px rgba(177, 156, 132, 0.28), -10px -10px 26px rgba(255, 255, 255, 0.82)',
        'clay-soft': '8px 8px 18px rgba(177, 156, 132, 0.2), -6px -6px 16px rgba(255, 255, 255, 0.75)',
        pressed: 'inset 6px 6px 14px rgba(177, 156, 132, 0.18), inset -6px -6px 12px rgba(255, 255, 255, 0.8)',
        float: '20px 20px 40px rgba(189, 166, 141, 0.18)',
      },
      animation: {
        fade: 'fade 0.5s ease forwards',
        float: 'float 7s ease-in-out infinite',
        shimmer: 'shimmer 2s linear infinite',
        pulseSoft: 'pulseSoft 3s ease-in-out infinite',
      },
      keyframes: {
        fade: {
          from: { opacity: '0', transform: 'translateY(12px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '0.55' },
          '50%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
};
