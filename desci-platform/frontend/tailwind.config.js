/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        /* shadcn/ui CSS variable-based color system */
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
          /* Extended Bioluminescent scale (backward compat) */
          50: "#ecfdf7",
          100: "#c6fce8",
          200: "#8df8d2",
          300: "#4debb8",
          400: "hsl(var(--primary))",
          500: "#00b894",
          600: "#009476",
          700: "#00755d",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
          light: "#818cf8",
          dark: "#4f46e5",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        /* DeSci-specific extended colors */
        surface: {
          DEFAULT: "#0a1628",
          raised: "#111d35",
          overlay: "#162444",
        },
        highlight: {
          DEFAULT: "#f0c040",
          light: "#fcd34d",
          dark: "#d4a017",
        },
        success: {
          DEFAULT: "#10b981",
          light: "#34d399",
          dark: "#059669",
        },
        warning: {
          DEFAULT: "#f59e0b",
          light: "#fbbf24",
          dark: "#d97706",
        },
        error: {
          DEFAULT: "#ef4444",
          light: "#f87171",
          dark: "#dc2626",
        },
        info: {
          DEFAULT: "#3b82f6",
          light: "#60a5fa",
          dark: "#2563eb",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
        "4xl": "2rem",
      },
      fontFamily: {
        display: ["Sora", "system-ui", "sans-serif"],
        sans: ["Lexend", "system-ui", "sans-serif"],
      },
      fontSize: {
        "display-1": ["3.5rem", { lineHeight: "1.05", fontWeight: "700", letterSpacing: "-0.03em" }],
        "display-2": ["2.5rem", { lineHeight: "1.1", fontWeight: "700", letterSpacing: "-0.025em" }],
        "heading-1": ["2rem", { lineHeight: "1.2", fontWeight: "600", letterSpacing: "-0.02em" }],
        "heading-2": ["1.5rem", { lineHeight: "1.25", fontWeight: "600", letterSpacing: "-0.015em" }],
        "heading-3": ["1.25rem", { lineHeight: "1.3", fontWeight: "600", letterSpacing: "-0.01em" }],
        "body-lg": ["1.125rem", { lineHeight: "1.65" }],
        "body": ["1rem", { lineHeight: "1.65" }],
        "body-sm": ["0.875rem", { lineHeight: "1.5" }],
        "caption": ["0.75rem", { lineHeight: "1.4", letterSpacing: "0.04em" }],
      },
      animation: {
        blob: "blob 12s ease-in-out infinite",
        "fade-in": "fadeIn 0.6s ease-out forwards",
        "slide-up": "slideUp 0.5s cubic-bezier(.16,1,.3,1) forwards",
        "slide-down": "slideDown 0.3s ease-out forwards",
        "scale-in": "scaleIn 0.3s cubic-bezier(.16,1,.3,1) forwards",
        "pulse-slow": "pulse 4s ease-in-out infinite",
        "shimmer": "shimmer 2.5s infinite linear",
        "spin-slow": "spin 4s linear infinite",
        "glow-pulse": "glowPulse 3s ease-in-out infinite",
        "float": "float 6s ease-in-out infinite",
        /* shadcn/ui standard animations */
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
      keyframes: {
        blob: {
          "0%, 100%": { transform: "translate(0px, 0px) scale(1)", opacity: "0.6" },
          "25%": { transform: "translate(40px, -60px) scale(1.15)", opacity: "0.8" },
          "50%": { transform: "translate(-30px, 40px) scale(0.85)", opacity: "0.5" },
          "75%": { transform: "translate(20px, -20px) scale(1.05)", opacity: "0.7" },
        },
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(24px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        slideDown: {
          "0%": { opacity: "0", transform: "translateY(-10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        scaleIn: {
          "0%": { opacity: "0", transform: "scale(0.92)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        glowPulse: {
          "0%, 100%": { opacity: "0.4", filter: "blur(40px)" },
          "50%": { opacity: "0.7", filter: "blur(60px)" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-12px)" },
        },
        /* shadcn/ui standard keyframes */
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
      },
      boxShadow: {
        "glass": "0 8px 32px rgba(0, 0, 0, 0.5)",
        "glass-lg": "0 16px 48px rgba(0, 0, 0, 0.6)",
        "glow-primary": "0 0 30px rgba(0, 212, 170, 0.15), 0 0 60px rgba(0, 212, 170, 0.05)",
        "glow-accent": "0 0 30px rgba(99, 102, 241, 0.15), 0 0 60px rgba(99, 102, 241, 0.05)",
        "glow-success": "0 0 20px rgba(16, 185, 129, 0.2)",
        "glow-error": "0 0 20px rgba(239, 68, 68, 0.2)",
        "inner-glow": "inset 0 1px 0 0 rgba(255, 255, 255, 0.05)",
      },
      backdropBlur: {
        xs: "2px",
      },
    },
  },
  plugins: [
    require("tailwindcss-animate"),
  ],
}
