import Popover from '../../shared/Popover';
import { tokens } from '../../shared/tokens';
import { rgbTripletToHex, hexToRgbTriplet } from '../colorFormat';

const WEEKDAY_OPTIONS = [
  { value: 0, label: 'Sunday' },
  { value: 1, label: 'Monday' },
  { value: 2, label: 'Tuesday' },
  { value: 3, label: 'Wednesday' },
  { value: 4, label: 'Thursday' },
  { value: 5, label: 'Friday' },
  { value: 6, label: 'Saturday' },
];

interface TodayHighlightSettingsProps {
  rgb: string;
  alpha: number;
  onChangeRgb: (rgb: string) => void;
  onChangeAlpha: (alpha: number) => void;
  recurringRgb: string;
  oneTimeRgb: string;
  onChangeRecurringRgb: (rgb: string) => void;
  onChangeOneTimeRgb: (rgb: string) => void;
  firstDayOfWeek: number;
  onChangeFirstDayOfWeek: (day: number) => void;
}

export default function TodayHighlightSettings({
  rgb,
  alpha,
  onChangeRgb,
  onChangeAlpha,
  recurringRgb,
  oneTimeRgb,
  onChangeRecurringRgb,
  onChangeOneTimeRgb,
  firstDayOfWeek,
  onChangeFirstDayOfWeek,
}: TodayHighlightSettingsProps) {
  return (
    <Popover label="Settings">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13 }}>
        <TodayColorField rgb={rgb} onChange={onChangeRgb} />
        <TodayAlphaField alpha={alpha} onChange={onChangeAlpha} />
        <ColorField
          id="event-color-recurring"
          label="Recurring event color"
          rgb={recurringRgb}
          onChange={onChangeRecurringRgb}
        />
        <ColorField
          id="event-color-one-time"
          label="One-time event color"
          rgb={oneTimeRgb}
          onChange={onChangeOneTimeRgb}
        />
        <FirstDayOfWeekField value={firstDayOfWeek} onChange={onChangeFirstDayOfWeek} />
      </div>
    </Popover>
  );
}

function FirstDayOfWeekField({ value, onChange }: { value: number; onChange: (day: number) => void }) {
  return (
    <label style={{ display: 'flex', alignItems: 'center', gap: 8 }} htmlFor="first-day-of-week">
      First day of week
      <select
        id="first-day-of-week"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        style={{ flex: 1 }}
      >
        {WEEKDAY_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function TodayColorField({ rgb, onChange }: { rgb: string; onChange: (rgb: string) => void }) {
  return <ColorField id="today-highlight-color" label="Today highlight color" rgb={rgb} onChange={onChange} />;
}

function ColorField({
  id,
  label,
  rgb,
  onChange,
}: {
  id: string;
  label: string;
  rgb: string;
  onChange: (rgb: string) => void;
}) {
  return (
    <label style={{ display: 'flex', alignItems: 'center', gap: 8 }} htmlFor={id}>
      {label}
      <input
        id={id}
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
