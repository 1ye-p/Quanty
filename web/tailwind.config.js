/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  '#eef2ff',
          100: '#e0e7ff',
          500: '#4f63d2',
          600: '#2d3561',
          700: '#1e2548',
        },
      },
    },
  },
  plugins: [],
}
