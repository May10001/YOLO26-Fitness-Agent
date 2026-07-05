/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Nike monochrome palette (DESIGN)
        obsidian: '#111111',
        paper: '#ffffff',
        concrete: '#e5e5e5',
        mist: '#f5f5f5',
        steel: '#707072',
        faint: '#9e9ea0',
        // Functional colors (retained — the only chroma, like Nike's product photos)
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
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'sans-serif'],
        display: ['Jost', 'Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
