import { useCallback } from 'react';
import { fetchAgentSessions } from '../../agents/api';
import { formatSeconds } from '../../agents/formatSeconds';
import { tokens } from '../../shared/tokens';
import { usePolling } from '../../shared/usePolling';

const POLL_SECONDS = 15;

// Lists live sessions only. A past session is followed from its /agents page, which links
// here with ?session=; it then shows as the selected option until the user picks another.
export default function SessionFollowPicker({
  followedId,
  followedTitle,
  followedLive,
  onFollow,
}: {
  followedId: string | null;
  followedTitle: string | null; // these two come from the followed session's records, once loaded
  followedLive: boolean | null;
  onFollow: (harnessId: string | null) => void;
}) {
  const fetcher = useCallback(() => fetchAgentSessions(), []);
  const { data: live } = usePolling(fetcher, POLL_SECONDS);
  const sessions = live ?? [];
  const followedIsListed = followedId === null || sessions.some((s) => s.id === followedId);
  return (
    <select
      value={followedId ?? ''}
      onChange={(e) => onFollow(e.target.value || null)}
      title="Show only the records one agent session has read or changed"
      style={{ ...tokens.input, width: '100%' }}
    >
      <option value="">follow a session…</option>
      {!followedIsListed && (
        <option value={followedId}>
          {followedTitle || followedId}
          {followedLive === false ? ' (ended)' : ''}
        </option>
      )}
      {sessions.map((s) => (
        <option key={s.id} value={s.id}>
          {s.title || s.id.slice(0, 8)} · {formatSeconds(s.age_seconds)}
        </option>
      ))}
    </select>
  );
}
