// A duration as its single largest whole unit (45s, 12m, 3h, 2d) -- the compact form the
// Agents table and the session page header both show for a session's age.
export function formatSeconds(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s}s`;
  const minutes = Math.floor(s / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.floor(hours / 24)}d`;
}
