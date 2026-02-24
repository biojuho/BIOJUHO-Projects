/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#4ade80', // Green-400
        secondary: '#facc15', // Yellow-400
        dark: '#1f2937', // Gray-800
      },
    },
  },
  plugins: [],
}
