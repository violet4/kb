// Conversion between the "r, g, b" triplet format useTodayHighlight stores (built for
// direct interpolation into rgba(${rgb}, ${alpha})) and the #rrggbb format <input
// type="color"> requires -- kept as pure functions, not inline in the settings
// component, per kb instructions #42 (data-and-logic).

export function rgbTripletToHex(rgb: string): string {
  const parts = rgb.split(',').map((n) => Number(n.trim()));
  if (parts.length !== 3 || parts.some(Number.isNaN)) return '#000000';
  return `#${parts.map((n) => Math.max(0, Math.min(255, n)).toString(16).padStart(2, '0')).join('')}`;
}

export function hexToRgbTriplet(hex: string): string {
  const match = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex);
  if (!match) return '0, 0, 0';
  const [, r, g, b] = match;
  return [r, g, b].map((h) => parseInt(h, 16)).join(', ');
}
