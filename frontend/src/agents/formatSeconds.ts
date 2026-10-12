// A duration to the minute (45s, 12m, 3h 7m, 2d 4h 30m), dropping zero units -- the form the
// Agents table and the session page header both show for a session's age.
export function formatSeconds(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s}s`;
  const totalMinutes = Math.floor(s / 60);
  const days = Math.floor(totalMinutes / 1440);
  const hours = Math.floor((totalMinutes % 1440) / 60);
  const minutes = totalMinutes % 60;
  const parts = [days && `${days}d`, hours && `${hours}h`, minutes && `${minutes}m`].filter(Boolean);
  return parts.join(' ');
}
