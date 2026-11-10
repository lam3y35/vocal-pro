/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        studio: {
          bg: "#0A0B10",
          surface: "#11131C",
          card: "#171A26",
          cardHover: "#1E2232",
          border: "#252B3D",
          borderHover: "#3A435E",
          primary: "#6C63FF",
          primaryHover: "#7E76FF",
          accent: "#00F0B5",
          accentHover: "#26F3C2",
          coral: "#FF4D6D",
          amber: "#FFB020",
          blue: "#38BDF8",
          purple: "#A855F7",
        },
      },
      boxShadow: {
        glowPrimary: "0 0 24px -4px rgba(108, 99, 255, 0.4)",
        glowAccent: "0 0 24px -4px rgba(0, 240, 181, 0.4)",
        glowCoral: "0 0 24px -4px rgba(255, 77, 109, 0.4)",
        glowAmber: "0 0 24px -4px rgba(255, 176, 32, 0.4)",
        card: "0 8px 30px -4px rgba(0, 0, 0, 0.45)",
      },
      animation: {
        shimmer: "shimmer 2.2s infinite linear",
        pulseSlow: "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        fadeIn: "fadeIn 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards",
      },
      keyframes: {
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        fadeIn: {
          "0%": { opacity: "0", transform: "translateY(5px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};
