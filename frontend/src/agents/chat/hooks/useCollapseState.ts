import { useCallback, useState } from 'react';
import type { AddressedBlock } from '../blockAddress';

interface UseCollapseStateResult {
  isCollapsed: (block: AddressedBlock, running: boolean) => boolean;
  toggle: (block: AddressedBlock, running: boolean) => void;
}

// Collapsed-by-default rule: text, and thinking unless the viewer hides it, start expanded,
// since they are the part of a transcript worth reading immediately; every other kind (tool
// calls/results and any future unrecognized block kind) starts collapsed as the bulky,
// skim-later part. A tool call still running starts expanded, so a long-running or hung call
// shows what it is doing; it collapses once its result arrives.
export function defaultCollapsed(block: AddressedBlock, showThinking: boolean, running: boolean): boolean {
  const kind = block.block.kind;
  return !(running || kind === 'text' || (kind === 'thinking' && showThinking));
}

// The default is derived from the block itself rather than from a map over every block, so
// isCollapsed keeps its identity while a live transcript appends messages and only changes
// when the user toggles something or changes showThinking.
export function useCollapseState(showThinking: boolean): UseCollapseStateResult {
  const [overrides, setOverrides] = useState<Map<string, boolean>>(new Map());

  const isCollapsed = useCallback(
    (block: AddressedBlock, running: boolean) =>
      overrides.get(block.id) ?? defaultCollapsed(block, showThinking, running),
    [overrides, showThinking],
  );

  const toggle = useCallback(
    (block: AddressedBlock, running: boolean) => {
      setOverrides((prev) => {
        const next = new Map(prev);
        next.set(block.id, !(prev.get(block.id) ?? defaultCollapsed(block, showThinking, running)));
        return next;
      });
    },
    [showThinking],
  );

  return { isCollapsed, toggle };
}
