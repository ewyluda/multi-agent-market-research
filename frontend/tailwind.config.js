/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'dark-bg': '#060911',
        'dark-card': '#111827',
        'dark-card-hover': '#1a2332',
        'dark-border': '#1f2937',
        'dark-border-accent': 'rgba(59, 130, 246, 0.3)',
        'dark-inset': '#080c15',
        'dark-elevated': '#1c2433',
        'accent-blue': '#3b82f6',
        'accent-green': '#10b981',
        'accent-red': '#ef4444',
        'accent-amber': '#f59e0b',
        'accent-purple': '#8b5cf6',
        'accent-cyan': '#06b6d4',
      },
    },
  },
  plugins: [],
}
