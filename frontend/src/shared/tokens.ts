// Theme Object pattern: single source of truth for non-layout styling
// (colors, etc). Plain typed constants -- see kb instructions #44
// (styling) for the full rationale and when CSS-variable-backed tokens
// would be worth the extra indirection instead.
export const tokens = {
  color: {
    background: '#111417',
    surface: '#1b1f24',
    border: '#2c3138',
    text: '#e6e9ec',
    textMuted: '#8b939c',
    accent: '#5b9dff',
    danger: '#e2574c',
    overdue: '#e2574c',
    due: '#e0a94c',
    barTrack: '#3a3f47',
    barFill: '#7c5cff',
  },
  // Shared style for any clickable text link (entity title links, external URLs,
  // nav items) -- no underline (distracting at this density), accent color instead
  // to distinguish it from plain body text.
  link: {
    color: '#5b9dff',
    textDecoration: 'none',
  } as const,
};
