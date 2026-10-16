import { useEffect, useState, type Dispatch, type SetStateAction } from 'react';

// How a value is written to and read from its localStorage string.
interface Codec {
  parse: (raw: string) => unknown;
  serialize: (value: unknown) => string;
}

const JSON_CODEC: Codec = { parse: JSON.parse, serialize: JSON.stringify };

// For a string preference stored as-is rather than JSON-quoted.
export const RAW_STRING: Codec = { parse: (raw) => raw, serialize: (value) => String(value) };

// useState that persists to localStorage under `key` -- the one implementation of a
// per-browser UI preference. A stored value that is missing, unparseable, or rejected by
// `isValid` falls back to `fallback`. Storage being unavailable (private browsing, blocked
// site data) leaves the preference working for the page load, just not persisted.
export function useStoredState<T>(
  key: string,
  fallback: T,
  isValid: (value: unknown) => value is T,
  codec: Codec = JSON_CODEC,
): [T, Dispatch<SetStateAction<T>>] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key);
      if (raw === null) return fallback;
      const parsed = codec.parse(raw);
      return isValid(parsed) ? parsed : fallback;
    } catch {
      return fallback;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(key, codec.serialize(value));
    } catch {
      // storage unavailable: keep the in-memory value only
    }
  }, [key, value, codec]);

  return [value, setValue];
}

export const isBoolean = (value: unknown): value is boolean => typeof value === 'boolean';
export const isString = (value: unknown): value is string => typeof value === 'string';
export const isPositiveNumber = (value: unknown): value is number => typeof value === 'number' && value > 0;
export const isNonNegativeNumber = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value) && value >= 0;
export const isHexColor = (value: unknown): value is string => typeof value === 'string' && /^#[0-9a-f]{6}$/i.test(value);
