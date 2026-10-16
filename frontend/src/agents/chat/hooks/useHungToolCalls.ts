import { useEffect, useMemo, useState } from 'react';
import type { ToolCallTime } from '../toolCallTimes';

export const NONE_HUNG: ReadonlySet<string> = new Set();

// The calls with no result yet, by id, each with the time it was written. A call whose message
// has no parseable timestamp counts as pending since forever.
function pendingSince(times: ReadonlyMap<string, ToolCallTime>): ReadonlyMap<string, number> {
  const pending = new Map<string, number>();
  for (const [id, { start, end }] of times) {
    if (end === null) pending.set(id, Number.isNaN(start) ? -Infinity : start);
  }
  return pending;
}

function sameMembers(a: ReadonlySet<string>, b: ReadonlySet<string>): boolean {
  return a.size === b.size && [...a].every((id) => b.has(id));
}

export interface HungToolCalls {
  // Pending for at least the threshold, by the browser's clock: no result has arrived yet.
  running: ReadonlySet<string>;
  // Answered, with a transcript duration (result timestamp minus call timestamp) of at least the
  // threshold.
  finished: ReadonlySet<string>;
  // running and finished together: every call that counts as hung.
  all: ReadonlySet<string>;
}

// A finished call's duration in the transcript decides whether it hung; it is derived from the
// times on every update rather than remembered from earlier renders. Remembering a call once
// the browser saw it pass the threshold is wrong: its result reaches the page a poll interval
// and a write later than it happened, so a call that took 1.9 s could look hung at 2 s by the
// browser's clock and then stay marked after its result showed it never was.
function finishedHung(times: ReadonlyMap<string, ToolCallTime>, thresholdMs: number): ReadonlySet<string> {
  const finished = new Set<string>();
  for (const [id, { start, end }] of times) {
    if (end !== null && end - start >= thresholdMs) finished.add(id);
  }
  return finished.size === 0 ? NONE_HUNG : finished;
}

// The tool calls, of any tool, that have hung: run for at least thresholdSeconds. Only a call
// that has been running that long is worth showing; a call that finishes sooner is never
// reported, so quick calls do not flash open and shut. While a call has no result, the browser's
// clock measures it, and a timer re-checks at the moment the next pending call crosses the
// threshold, so a call is reported on time even when no new transcript data arrives.
export function useHungToolCalls(times: ReadonlyMap<string, ToolCallTime>, thresholdSeconds: number): HungToolCalls {
  const pending = useMemo(() => pendingSince(times), [times]);
  const [hung, setHung] = useState<ReadonlySet<string>>(NONE_HUNG);

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
  const finished = useMemo(() => finishedHung(times, thresholdSeconds * 1000), [times, thresholdSeconds]);
  return useMemo(
    () => ({ running, finished, all: finished.size === 0 ? running : new Set([...running, ...finished]) }),
    [running, finished],
  );
}
