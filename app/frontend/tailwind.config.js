/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        arsenal: {
          red: "#EF0107",
          "red-dark": "#C30000",
          navy: "#063672",
          "navy-dark": "#042B5C",
          gold: "#9C824A",
          "gold-light": "#C5A55A",
          white: "#FFFFFF",
          black: "#1B1B1B",
        },
        surface: {
          50: "#fafafa",
          100: "#f4f4f5",
          200: "#e4e4e7",
          300: "#d4d4d8",
          600: "#52525b",
          700: "#3f3f46",
          800: "#27272a",
          900: "#18181b",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        display: ['"Bebas Neue"', "Impact", "sans-serif"],
        clock: ['"Share Tech Mono"', "ui-monospace", "monospace"],
      },
      keyframes: {
        "ken-burns": {
          "0%, 100%": { transform: "scale(1.0)" },
          "50%": { transform: "scale(1.04)" },
        },
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "ken-burns": "ken-burns 45s ease-in-out infinite",
      },
      boxShadow: {
        card: "0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)",
        "card-hover": "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)",
        "glass-sm": "0 4px 16px 0 rgb(0 0 0 / 0.10), inset 0 1px 0 0 rgb(255 255 255 / 0.08)",
        glass: "0 8px 32px 0 rgb(0 0 0 / 0.18), inset 0 1px 0 0 rgb(255 255 255 / 0.10)",
        "glass-lg": "0 12px 48px 0 rgb(0 0 0 / 0.22), inset 0 1px 0 0 rgb(255 255 255 / 0.12)",
        "glass-glow": "0 8px 32px 0 rgb(239 1 7 / 0.15), 0 0 0 1px rgb(255 255 255 / 0.08)",
      },
      backdropBlur: {
        xs: "2px",
        "3xl": "64px",
      },
    },
  },
  plugins: [],
};
