/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        paper: {
          DEFAULT: '#ecece3',
          deep: '#e5e5dc',
          surface: '#f4f3ed',
        },
        forest: {
          DEFAULT: '#2c3e2e',
          deep: '#233325',
          soft: '#e0e7df',
        },
        severity: {
          low: '#4c614e',
          medium: '#80591d',
          high: '#963c30',
          critical: '#963c30',
          resolved: '#416b4a',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        serif: ['Playfair Display', 'Georgia', 'serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      }
    },
  },
  plugins: [],
}
