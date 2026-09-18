import { useEffect, useState } from 'react';

const API_BASE = '/api';

// The one name every page that can send a Channel message (currently just the Agents chat
// view) attaches to an outgoing message as its sender -- backed by Settings.display_name
// (DB), not per-device storage, so it's the same everywhere the person opens the UI. No
// hardcoded fallback: an unset name means the settings input renders empty until the
// person fills it in.
export function useDisplayName(): [string, (value: string) => void] {
  const [displayName, setDisplayNameState] = useState('');

  useEffect(() => {
    fetch(`${API_BASE}/settings`)
      .then((r) => r.json())
      .then((data) => setDisplayNameState(data.display_name ?? ''));
  }, []);

  const setDisplayName = (value: string) => {
    setDisplayNameState(value);
    fetch(`${API_BASE}/settings`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_name: value }),
    });
  };

  return [displayName, setDisplayName];
}
