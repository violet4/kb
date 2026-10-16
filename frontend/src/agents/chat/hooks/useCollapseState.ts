import { useCallback, useState } from 'react';
import type { AddressedBlock } from '../blockAddress';

interface UseCollapseStateResult {
  isCollapsed: (block: AddressedBlock, hung: boolean) => boolean;
  toggle: (block: AddressedBlock, hung: boolean) => void;
}

// Collapsed-by-default rule: text, and thinking unless the viewer hides it, start expanded,
// since they are the part of a transcript worth reading immediately; every other kind (tool
// calls/results and any future unrecognized block kind) starts collapsed as the bulky,
// skim-later part. Text the harness injected on the user's turn (tagged isMeta, such as a
// loaded skill's instructions) is bulky too, so it starts collapsed like a tool result. A hung
// tool call (pending past the viewer's threshold, see useHungToolCalls) starts expanded, so it
// shows what it is stuck on; it collapses again once its result arrives, since a finished
// call's content matters no more than any other's.
export function defaultCollapsed(block: AddressedBlock, showThinking: boolean, hung: boolean): boolean {
  const { kind, tags } = block.block;
  const readable = (kind === 'text' && tags.isMeta !== 'true') || (kind === 'thinking' && showThinking);
  return !(hung || readable);
}

// The default is derived from the block itself rather than from a map over every block, so
// isCollapsed keeps its identity while a live transcript appends messages and only changes
// when the user toggles something or changes showThinking.
export function useCollapseState(showThinking: boolean): UseCollapseStateResult {
  const [overrides, setOverrides] = useState<Map<string, boolean>>(new Map());

  const isCollapsed = useCallback(
    (block: AddressedBlock, hung: boolean) => overrides.get(block.id) ?? defaultCollapsed(block, showThinking, hung),
    [overrides, showThinking],
  );

  const toggle = useCallback(
    (block: AddressedBlock, hung: boolean) => {
      setOverrides((prev) => {
        const next = new Map(prev);
        next.set(block.id, !(prev.get(block.id) ?? defaultCollapsed(block, showThinking, hung)));
        return next;
      });
    },
    [showThinking],
  );

  return { isCollapsed, toggle };
}
