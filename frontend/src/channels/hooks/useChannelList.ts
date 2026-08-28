import { useCallback } from 'react';
import { usePolling } from '../../shared/usePolling';
import { fetchChannels } from '../api';
import type { ChannelSummary } from '../types';

interface UseChannelListResult {
  channels: ChannelSummary[];
  error: string | null;
  refresh: () => void;
}

// refresh() lets a caller force an immediate re-fetch (e.g. right after sending a DM's first
// message, so the newly-created channel_id shows up without waiting up to intervalSeconds for
// the next scheduled poll). See usePolling for the shared, generation-scoped poll mechanism.
export function useChannelList(displayName: string, intervalSeconds: number): UseChannelListResult {
  const fetcher = useCallback(() => fetchChannels(displayName), [displayName]);
  const { data, error, refresh } = usePolling(fetcher, intervalSeconds);
  return { channels: data ?? [], error, refresh };
}
