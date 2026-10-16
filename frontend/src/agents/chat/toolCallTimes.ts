import type { TranscriptEntry } from './hooks/useSessionChat';

// When one tool call was written and when its result was, in ms since the epoch, both from the
// transcript's own timestamps: the harness writes a call before running it and its result once
// it finishes. end is null while the call is pending (or, in a session that ended mid-call,
// never answered). Either is NaN when its message has no parseable timestamp.
export interface ToolCallTime {
  start: number;
  end: number | null;
}

export function toolCallTimes(entries: TranscriptEntry[]): ReadonlyMap<string, ToolCallTime> {
  const times = new Map<string, ToolCallTime>();
  for (const { message, blocks } of entries) {
    const at = Date.parse(message.timestamp);
    for (const { block } of blocks) {
      if (block.tool_use_id === null) continue;
      if (block.kind === 'tool_use') times.set(block.tool_use_id, { start: at, end: null });
      else if (block.kind === 'tool_result') {
        const call = times.get(block.tool_use_id);
        if (call) call.end = at;
      }
    }
  }
  return times;
}

// A tool call's duration: tenths of a second under 10 s, whole seconds under a minute, then
// minute-and-second (or hour-and-minute) pairs -- 4.2s, 42s, 1m 12s, 2h 5m.
export function formatCallDuration(ms: number): string {
  const seconds = Math.max(0, ms) / 1000;
  if (seconds < 10) return `${seconds.toFixed(1)}s`;
  const s = Math.floor(seconds);
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`;
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
}
