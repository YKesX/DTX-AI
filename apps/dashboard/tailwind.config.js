/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        ink: '#111111',
        muted: '#474747',
        dim: '#65655f',
        paper: '#f3f3ef',
        'paper-selected': '#e8e8e2',
        line: 'rgba(17, 17, 17, 0.12)',
      },
      fontFamily: {
        serif: ['Iowan Old Style', 'Palatino Linotype', 'Book Antiqua', 'serif'],
        mono: ['SFMono-Regular', 'IBM Plex Mono', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
}
