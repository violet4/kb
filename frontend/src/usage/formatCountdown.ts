// Formats a duration (ms) as the largest-unit-first "Dd HHh MMm" countdown
// used by UsageBar, dropping leading zero units (0h 5m, not 0h 05m -- but
// e.g. 2h 05m keeps the leading zero on the smaller unit once a larger one
// is shown, so the width doesn't jitter as minutes tick over).
export function formatCountdown(ms: number): string {
  const totalMinutes = Math.max(0, Math.round(ms / 60_000));
  const days = Math.floor(totalMinutes / (24 * 60));
  const hours = Math.floor((totalMinutes % (24 * 60)) / 60);
  const minutes = totalMinutes % 60;

  if (days > 0) return `${days}d ${hours}h ${String(minutes).padStart(2, '0')}m`;
  if (hours > 0) return `${hours}h ${String(minutes).padStart(2, '0')}m`;
  return `${minutes}m`;
}

export function formatResetsAtTooltip(resetsAtIso: string): string {
  return `Resets ${new Date(resetsAtIso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })}`;
}
