// ISO 8601 display of an API timestamp (UTC, zone-stamped) in the viewer's local time.
const pad = (n: number) => String(n).padStart(2, '0');

export function isoDate(utc: string | null): string {
  if (!utc) return '';
  const d = new Date(utc);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function isoDateTime(utc: string | null): string {
  if (!utc) return '';
  const d = new Date(utc);
  return `${isoDate(utc)} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
