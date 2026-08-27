import { useEffect, useState } from 'react';

const STORAGE_KEY = 'kb-display-name';
export const DEFAULT_DISPLAY_NAME = 'violet';

// The one name every page that can send a Channel message (currently just the Agents chat
// view) attaches to an outgoing message as its sender -- shared here, not per-page, so
// setting it once in Settings applies everywhere a message can be sent.
export function useDisplayName(): [string, (value: string) => void] {
  const [displayName, setDisplayNameState] = useState(() => localStorage.getItem(STORAGE_KEY) || DEFAULT_DISPLAY_NAME);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, displayName);
  }, [displayName]);

  return [displayName, setDisplayNameState];
}
