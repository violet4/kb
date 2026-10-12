// Theme Object pattern: single source of truth for non-layout styling
// (colors, etc). Plain typed constants -- see kb instructions #44
// (styling) for the full rationale and when CSS-variable-backed tokens
// would be worth the extra indirection instead.
const color = {
  background: '#111417',
  surface: '#1b1f24',
  revealed: '#18222e', // a row shown only temporarily, e.g. a drop target revealed during a drag
  border: '#2c3138',
  text: '#e6e9ec',
  textMuted: '#8b939c',
  accent: '#5b9dff',
  danger: '#e2574c',
  overdue: '#e2574c',
  due: '#e0a94c',
  barTrack: '#3a3f47',
  barFill: '#7c5cff',
};

export const tokens = {
  color,
  // Shared style for any clickable text link (entity title links, external URLs,
  // nav items) -- no underline (distracting at this density), accent color instead
  // to distinguish it from plain body text. Sets both the shorthand and the
  // longhand textDecorationLine -- Firefox has been observed still showing the
  // UA-stylesheet underline on <a> with only the shorthand set inline, even though
  // Chrome honors it; the explicit longhand is what actually suppresses it there.
  link: {
    color: '#5b9dff',
    textDecoration: 'none',
    textDecorationLine: 'none',
  } as const,
  // A compact text input inside a list (new context name, quick-add title).
  input: {
    background: color.surface,
    color: color.text,
    border: `1px solid ${color.border}`,
    borderRadius: 4,
    padding: '4px 8px',
    fontSize: 13,
  } as const,
  // A borderless one-glyph button (a "+") placed next to the thing it acts on.
  glyphButton: {
    padding: '0 4px',
    border: 'none',
    background: 'none',
    color: color.textMuted,
    cursor: 'pointer',
    fontSize: 13,
    lineHeight: 1,
  } as const,
};
