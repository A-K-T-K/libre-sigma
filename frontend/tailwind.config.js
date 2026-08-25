/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Segoe UI', 'Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['Consolas', 'Menlo', 'Monaco', 'Courier New', 'monospace'],
      },
      colors: {
        minitab: {
          50: '#f0f5fa',
          100: '#e1ecf5',
          200: '#c3d9eb',
          300: '#94bcdd',
          400: '#5e9bc9',
          500: '#3b80b2',
          600: '#2b6594',
          700: '#235178',
          800: '#1e4564',
          900: '#1d3b53',
          950: '#132637',
        }
      }
    },
  },
  plugins: [],
}
