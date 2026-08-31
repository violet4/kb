import { useState } from 'react';
import type { RecurrencePreset } from '../recurrencePresets';
import { rruleForPreset } from '../recurrencePresets';

interface UseRecurrenceFieldResult {
  preset: RecurrencePreset;
  everyN: number;
  rrule: string;
  setPreset: (preset: RecurrencePreset) => void;
  setEveryN: (n: number) => void;
  setRruleDirect: (rrule: string) => void;
}

/** Tracks the recurrence preset dropdown, its 'every N days' companion number input,
 * and the raw RRULE string those two drive -- picking a preset overwrites rrule with
 * the preset's generated string; typing directly into the raw textbox (setRruleDirect)
 * switches the preset to 'custom' so the two controls never silently disagree about
 * what the field currently holds. */
export function useRecurrenceField(date: Date): UseRecurrenceFieldResult {
  const [preset, setPresetState] = useState<RecurrencePreset>('none');
  const [everyN, setEveryNState] = useState(2);
  const [rrule, setRrule] = useState('');

  const setPreset = (next: RecurrencePreset): void => {
    setPresetState(next);
    if (next !== 'custom') setRrule(rruleForPreset(next, date, everyN));
  };

  const setEveryN = (n: number): void => {
    setEveryNState(n);
    if (preset === 'every-n-days') setRrule(rruleForPreset('every-n-days', date, n));
  };

  const setRruleDirect = (next: string): void => {
    setRrule(next);
    setPresetState('custom');
  };

  return { preset, everyN, rrule, setPreset, setEveryN, setRruleDirect };
}
