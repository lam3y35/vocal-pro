/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        studio: {
          bg: "#0F1016",
          card: "#161822",
          border: "#25293A",
          primary: "#6C63FF",
          accent: "#00D4AA",
          coral: "#FF5E7E",
          amber: "#FFB800",
        },
      },
    },
  },
  plugins: [],
};
