/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        void: 'var(--cp-bg-void)',
        panel: 'var(--cp-bg-panel)',
        cyan: 'var(--cp-accent-cyan)',
        violet: 'var(--cp-accent-violet)',
        mint: 'var(--cp-accent-mint)',
        amber: 'var(--cp-accent-amber)',
        rose: 'var(--cp-accent-rose)',
        mist: 'var(--cp-text-primary)',
        muted: 'var(--cp-text-muted)',
        hair: 'var(--cp-border-hair)',
      },
      fontFamily: {
        display: ['var(--cp-font-display)'],
        body: ['var(--cp-font-body)'],
      },
    },
  },
  plugins: [],
};
