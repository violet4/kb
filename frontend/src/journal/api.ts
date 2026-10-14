import { checked } from '../shared/http';
import type { TimelinePage } from './types';

export async function fetchTimeline(before: number | null, includeReads: boolean): Promise<TimelinePage> {
  const params = new URLSearchParams({ include_reads: String(includeReads) });
  if (before !== null) params.set('before', String(before));
  const path = `/journal?${params}`;
  return checked(await fetch(`/api${path}`), path);
}
