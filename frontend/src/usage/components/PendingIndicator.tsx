import { useEffect, useState } from 'react';
import { tokens } from '../../shared/tokens';

interface PendingIndicatorProps {
  requestStartedAt: number;
}

// Ticks while a request is in flight so a slow backend (the claude CLI subprocess this
// endpoint shells out to routinely takes several seconds) shows visible progress instead of
// a blank panel with no feedback until the response finally lands.
export default function PendingIndicator({ requestStartedAt }: PendingIndicatorProps) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(interval);
  }, []);

  const seconds = Math.max(0, (now - requestStartedAt) / 1000);
  return (
    <p style={{ margin: 0, color: tokens.color.textMuted }}>Loading... ({seconds.toFixed(1)}s)</p>
  );
}
