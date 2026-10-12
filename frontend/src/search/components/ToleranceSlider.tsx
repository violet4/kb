import { tokens } from '../../shared/tokens';

// How far a semantic match may be from the query (cosine distance). Higher is more tolerant:
// more, looser results. Exact-text matches are unaffected.
export default function ToleranceSlider({ value, onChange }: { value: number; onChange: (value: number) => void }) {
  return (
    <label
      title="Maximum embedding cosine distance for meaning-based matches; higher includes looser matches. Exact-text matches are always kept."
      style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: tokens.color.textMuted }}
    >
      tolerance
      <input
        type="range"
        min={0.5}
        max={1}
        step={0.01}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        style={{ width: 110 }}
      />
      <span style={{ fontVariantNumeric: 'tabular-nums', minWidth: 28 }}>{value.toFixed(2)}</span>
    </label>
  );
}
