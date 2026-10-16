import { useEffect, useMemo, useState } from 'react';
import type { TranscriptEntry } from './useSessionChat';

export const NONE_HUNG: ReadonlySet<string> = new Set();

// The tool calls with no tool_result yet, by id, each with the time it was written: the harness
// writes a call to the transcript before running it and its result only once it finishes, so
// these are the calls still running (or, in a session that ended mid-call, never answered). A
// call whose message has no parseable timestamp counts as pending since forever.
function pendingToolCalls(entries: TranscriptEntry[]): ReadonlyMap<string, number> {
  const pending = new Map<string, number>();
  for (const { message, blocks } of entries) {
    const since = Date.parse(message.timestamp);
    for (const { block } of blocks) {
      if (block.tool_use_id === null) continue;
      if (block.kind === 'tool_use') pending.set(block.tool_use_id, Number.isNaN(since) ? -Infinity : since);
      else if (block.kind === 'tool_result') pending.delete(block.tool_use_id);
    }
  }
  return pending;
}

function sameMembers(a: ReadonlySet<string>, b: ReadonlySet<string>): boolean {
  return a.size === b.size && [...a].every((id) => b.has(id));
}

export interface HungToolCalls {
  // Hung and still pending.
  running: ReadonlySet<string>;
  // Every call that has hung while this transcript was open, finished or not.
  ever: ReadonlySet<string>;
}

// The tool calls, of any tool, that have been pending for at least thresholdSeconds: a call
// that has been running that long is hanging, and only then is what it is doing worth showing.
// A call that finishes sooner is never reported, so quick calls do not flash open and shut. A
// timer re-checks at the moment the next pending call crosses the threshold, so a call is
// reported on time even when no new transcript data arrives.
export function useHungToolCalls(entries: TranscriptEntry[], thresholdSeconds: number): HungToolCalls {
  const pending = useMemo(() => pendingToolCalls(entries), [entries]);
  const [hung, setHung] = useState<ReadonlySet<string>>(NONE_HUNG);
  const [ever, setEver] = useState<ReadonlySet<string>>(NONE_HUNG);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const thresholdMs = thresholdSeconds * 1000;
    const check = () => {
      const now = Date.now();
      const next = new Set<string>();
      let soonest = Infinity;
      for (const [id, since] of pending) {
        const hangsAt = since + thresholdMs;
        if (hangsAt <= now) next.add(id);
        else soonest = Math.min(soonest, hangsAt);
      }
      setHung((prev) => (sameMembers(prev, next) ? prev : next.size === 0 ? NONE_HUNG : next));
      setEver((prev) => ([...next].every((id) => prev.has(id)) ? prev : new Set([...prev, ...next])));
      if (soonest !== Infinity) timer = setTimeout(check, soonest - now);
    };
    check();
    return () => clearTimeout(timer);
  }, [pending, thresholdSeconds]);

  // A call answered since the last check is no longer running, even before the effect re-checks.
  const running = useMemo(() => {
    if ([...hung].every((id) => pending.has(id))) return hung;
    const current = new Set([...hung].filter((id) => pending.has(id)));
    return current.size === 0 ? NONE_HUNG : current;
  }, [hung, pending]);
  return useMemo(() => ({ running, ever }), [running, ever]);
}
