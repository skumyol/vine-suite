import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: 'hsl(var(--bg))',
          subtle: 'hsl(var(--bg-subtle))',
          muted: 'hsl(var(--bg-muted))',
        },
        surface: {
          DEFAULT: 'hsl(var(--surface))',
          elevated: 'hsl(var(--surface-elevated))',
        },
        fg: {
          DEFAULT: 'hsl(var(--fg))',
          muted: 'hsl(var(--fg-muted))',
          subtle: 'hsl(var(--fg-subtle))',
        },
        border: {
          DEFAULT: 'hsl(var(--border))',
          strong: 'hsl(var(--border-strong))',
        },
        ring: 'hsl(var(--ring))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          fg: 'hsl(var(--primary-fg))',
          soft: 'hsl(var(--primary-soft))',
        },
        success: {
          DEFAULT: 'hsl(var(--success))',
          soft: 'hsl(var(--success-soft))',
        },
        warning: {
          DEFAULT: 'hsl(var(--warning))',
          soft: 'hsl(var(--warning-soft))',
        },
        danger: {
          DEFAULT: 'hsl(var(--danger))',
          soft: 'hsl(var(--danger-soft))',
        },
        info: {
          DEFAULT: 'hsl(var(--info))',
          soft: 'hsl(var(--info-soft))',
        },
        sidebar: {
          bg: 'hsl(var(--sidebar-bg))',
          border: 'hsl(var(--sidebar-border))',
          fg: 'hsl(var(--sidebar-fg))',
          'fg-active': 'hsl(var(--sidebar-fg-active))',
          hover: 'hsl(var(--sidebar-hover))',
          active: 'hsl(var(--sidebar-active))',
        },
      },
      borderRadius: {
        lg: '12px',
        md: '8px',
        sm: '6px',
      },
      fontFamily: {
        sans: ['var(--font-inter)', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
      },
      boxShadow: {
        'subtle': '0 1px 2px rgba(0,0,0,0.04)',
        'card': '0 1px 2px rgba(0,0,0,0.04), 0 8px 32px -12px rgba(0,0,0,0.08)',
        'glow-primary': '0 0 0 4px hsl(var(--primary) / 0.12)',
      },
    },
  },
  plugins: [],
};

export default config;
