import type { Config } from "tailwindcss";

// "Dispatch" — semantic colors key off the CSS custom properties in
// src/app/globals.css (hsl(var(--token) / <alpha>)), so light/dark retheme for
// free.
const withVar = (v: string) => `hsl(var(--${v}) / <alpha-value>)`;

export default {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        border: withVar("border"),
        input: withVar("input"),
        ring: withVar("ring"),
        background: withVar("background"),
        foreground: withVar("foreground"),
        primary: { DEFAULT: withVar("primary"), foreground: withVar("primary-foreground") },
        secondary: { DEFAULT: withVar("secondary"), foreground: withVar("secondary-foreground") },
        muted: { DEFAULT: withVar("muted"), foreground: withVar("muted-foreground") },
        accent: { DEFAULT: withVar("accent"), foreground: withVar("accent-foreground") },
        card: { DEFAULT: withVar("card"), foreground: withVar("card-foreground") },
        popover: { DEFAULT: withVar("popover"), foreground: withVar("popover-foreground") },
        brand: { DEFAULT: withVar("brand"), foreground: withVar("brand-foreground") },
        code: { DEFAULT: withVar("code"), foreground: withVar("code-foreground") },
        success: { DEFAULT: withVar("success"), foreground: withVar("success-foreground") },
        warning: { DEFAULT: withVar("warning"), foreground: withVar("warning-foreground") },
        info: { DEFAULT: withVar("info"), foreground: withVar("info-foreground") },
        destructive: {
          DEFAULT: withVar("destructive"),
          foreground: withVar("destructive-foreground"),
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)"],
        display: ["var(--font-display)"],
        mono: ["var(--font-mono)"],
      },
      borderRadius: {
        sm: "calc(var(--radius) - 4px)",
        md: "calc(var(--radius) - 2px)",
        lg: "var(--radius)",
        xl: "0.75rem",
        "2xl": "1rem",
      },
      boxShadow: {
        xs: "0 1px 2px 0 hsl(30 22% 10% / 0.06)",
        sm: "0 1px 3px 0 hsl(30 22% 10% / 0.09), 0 1px 2px -1px hsl(30 22% 10% / 0.06)",
        md: "0 4px 12px -2px hsl(30 22% 10% / 0.12), 0 2px 6px -2px hsl(30 22% 10% / 0.07)",
        lg: "0 12px 28px -6px hsl(30 22% 10% / 0.16), 0 6px 12px -6px hsl(30 22% 10% / 0.09)",
        brand: "0 8px 24px -6px hsl(var(--brand) / 0.40)",
      },
    },
  },
  plugins: [],
} satisfies Config;
