import { useEffect, useState } from 'react';

// useState that persists to localStorage under `key` -- a per-browser UI preference. A stored
// value that is missing, unparseable, or rejected by `isValid` falls back to `fallback`.
export function useStoredState<T>(key: string, fallback: T, isValid: (value: unknown) => value is T): [T, (value: T) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key);
      const parsed: unknown = raw === null ? null : JSON.parse(raw);
      return isValid(parsed) ? parsed : fallback;
    } catch {
      return fallback;
    }
  });

  useEffect(() => {
    localStorage.setItem(key, JSON.stringify(value));
  }, [key, value]);

  return [value, setValue];
}

export const isBoolean = (value: unknown): value is boolean => typeof value === 'boolean';
