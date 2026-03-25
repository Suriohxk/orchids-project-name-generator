/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        cyber: {
          50:  '#f0fdf4',
          100: '#dcfce7',
          400: '#4ade80',
          500: '#22c55e',
          900: '#14532d',
        },
        danger: {
          400: '#f87171',
          500: '#ef4444',
          600: '#dc2626',
        },
        warn: {
          400: '#fb923c',
          500: '#f97316',
        },
        dark: {
          900: '#030712',
          800: '#0f172a',
          700: '#1e293b',
          600: '#334155',
          500: '#475569',
          400: '#64748b',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}
