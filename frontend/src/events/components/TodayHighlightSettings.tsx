import Popover from '../../shared/Popover';
import { tokens } from '../../shared/tokens';
import { rgbTripletToHex, hexToRgbTriplet } from '../colorFormat';

interface TodayHighlightSettingsProps {
  rgb: string;
  alpha: number;
  onChangeRgb: (rgb: string) => void;
  onChangeAlpha: (alpha: number) => void;
}

export default function TodayHighlightSettings({
  rgb,
  alpha,
  onChangeRgb,
  onChangeAlpha,
}: TodayHighlightSettingsProps) {
  return (
    <Popover label="Settings">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13 }}>
        <TodayColorField rgb={rgb} onChange={onChangeRgb} />
        <TodayAlphaField alpha={alpha} onChange={onChangeAlpha} />
      </div>
    </Popover>
  );
}

function TodayColorField({ rgb, onChange }: { rgb: string; onChange: (rgb: string) => void }) {
  return (
    <label style={{ display: 'flex', alignItems: 'center', gap: 8 }} htmlFor="today-highlight-color">
      Today highlight color
      <input
        id="today-highlight-color"
        type="color"
        value={rgbTripletToHex(rgb)}
        onChange={(e) => onChange(hexToRgbTriplet(e.target.value))}
        style={{ width: 32, height: 24, padding: 0, border: `1px solid ${tokens.color.border}`, borderRadius: 4 }}
      />
    </label>
  );
}

function TodayAlphaField({ alpha, onChange }: { alpha: number; onChange: (alpha: number) => void }) {
  return (
    <label style={{ display: 'flex', alignItems: 'center', gap: 8 }} htmlFor="today-highlight-alpha">
      Intensity
      <input
        id="today-highlight-alpha"
        type="range"
        min={0}
        max={1}
        step={0.05}
        value={alpha}
        onChange={(e) => onChange(Number(e.target.value))}
        style={{ flex: 1 }}
      />
      <span style={{ width: 32, textAlign: 'right' }}>{Math.round(alpha * 100)}%</span>
    </label>
  );
}
