// Re-export the design tokens for runtime use (mirrors _tokens.scss).
export const tokens = {
  color: {
    primary: '#2f6fed',
    success: '#1aa260',
    warning: '#f59e0b',
    danger: '#dc2626',
    info: '#0ea5e9',
    neutral900: '#0f172a',
    neutral700: '#334155',
    neutral500: '#64748b',
    neutral300: '#cbd5e1',
    neutral100: '#f1f5f9',
    surface: '#ffffff',
  },
  space: { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 },
  radius: { sm: 4, md: 6, lg: 10 },
  z: { dropdown: 1000, sticky: 1020, fixed: 1030, modalBackdrop: 1040, modal: 1050, toast: 1080 },
};
