/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'dark-bg': '#000000',
        'dark-card': '#18181b',
        'dark-card-hover': '#27272a',
        'dark-border': '#27272a',
        'dark-border-accent': 'rgba(0, 111, 238, 0.3)',
        'dark-inset': '#09090b',
        'dark-elevated': '#27272a',
        'accent-blue': '#006fee',
        'accent-green': '#17c964',
        'accent-red': '#f31260',
        'accent-amber': '#f5a524',
        'accent-purple': '#7828c8',
        'accent-cyan': '#338ef7',
      },
    },
  },
  plugins: [],
}
