import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Brand (indigo) — CTAs, links, focus, trust.
        brand: {
          DEFAULT: "#4f46e5",
          dark: "#4338ca",
          light: "#eef2ff",
          fg: "#ffffff",
        },
        // Deal (amber) — prices, %-off, urgency. The conversion accent.
        deal: {
          DEFAULT: "#f59e0b",
          dark: "#b45309",
          light: "#fffbeb",
          fg: "#78350f",
        },
        success: "#059669",
        warning: "#d97706",
        danger: "#e11d48",
        ink: "#18181b",
        paper: "#fafafa",
      },
      fontFamily: {
        sans: [
          "var(--font-inter)",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
      },
      boxShadow: {
        card: "0 1px 2px rgb(24 24 27 / 0.04), 0 1px 3px rgb(24 24 27 / 0.06)",
        "card-hover": "0 6px 16px rgb(24 24 27 / 0.10), 0 2px 6px rgb(24 24 27 / 0.06)",
        pop: "0 12px 32px rgb(24 24 27 / 0.14)",
      },
      borderRadius: {
        card: "0.75rem",
      },
      keyframes: {
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        shimmer: "shimmer 1.4s infinite",
      },
    },
  },
  plugins: [],
};
export default config;
