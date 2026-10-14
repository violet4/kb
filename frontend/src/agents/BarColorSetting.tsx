import { tokens } from '../shared/tokens';

// One-click choices from the page's own palette, plus a picker for any other color.
const SWATCHES = [
  { label: 'Gray', color: tokens.color.textMuted },
  { label: 'Green', color: tokens.color.shellPrompt },
  { label: 'Orange', color: tokens.color.due },
  { label: 'Purple', color: tokens.color.barFill },
];

interface BarColorSettingProps {
  value: string; // #rrggbb
  onChange: (color: string) => void;
}

export default function BarColorSetting({ value, onChange }: BarColorSettingProps) {
  return (
    <div role="group" aria-label="Bar color" style={{ display: 'flex', alignItems: 'center', gap: 6, paddingLeft: 22 }}>
      {SWATCHES.map((swatch) => {
        const selected = swatch.color.toLowerCase() === value.toLowerCase();
        return (
          <button
            key={swatch.label}
            type="button"
            onClick={() => onChange(swatch.color)}
            aria-label={swatch.label}
            aria-pressed={selected}
            title={swatch.label}
            style={{
              width: 18,
              height: 18,
              padding: 0,
              borderRadius: 4,
              border: `2px solid ${selected ? tokens.color.text : 'transparent'}`,
              background: swatch.color,
              cursor: 'pointer',
            }}
          />
        );
      })}
      <input
        type="color"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label="Custom bar color"
        title="Custom color"
        style={{ width: 26, height: 22, padding: 0, border: 'none', background: 'transparent', cursor: 'pointer' }}
      />
    </div>
  );
}
