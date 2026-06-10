/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        flame: '#ff6a00',
        rose: '#ee0979',
        success: '#38ef7d',
        danger: '#ff4d4d',
        dark: {
          900: '#0a0a0a',
          800: '#111111',
          700: '#1a1a1a',
          600: '#2a2a2a',
        },
      },
    },
  },
  plugins: [],
}
