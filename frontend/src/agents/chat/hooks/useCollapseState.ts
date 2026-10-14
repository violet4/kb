import { useCallback, useState } from 'react';
import type { AddressedBlock } from '../blockAddress';

interface UseCollapseStateResult {
  isCollapsed: (block: AddressedBlock) => boolean;
  toggle: (block: AddressedBlock) => void;
}

// Collapsed-by-default rule: text and thinking start expanded, since they are the part of a
// transcript worth reading immediately; every other kind (tool calls/results and any future
// unrecognized block kind) starts collapsed as the bulky, skim-later part.
const EXPANDED_KINDS: ReadonlySet<string> = new Set(['text', 'thinking']);

export function defaultCollapsed(block: AddressedBlock): boolean {
  return !EXPANDED_KINDS.has(block.block.kind);
}

// The default is derived from the block itself rather than from a map over every block, so
// isCollapsed keeps its identity while a live transcript appends messages and only changes
// when the user actually toggles something.
export function useCollapseState(): UseCollapseStateResult {
  const [overrides, setOverrides] = useState<Map<string, boolean>>(new Map());

  const isCollapsed = useCallback(
    (block: AddressedBlock) => overrides.get(block.id) ?? defaultCollapsed(block),
    [overrides],
  );

  const toggle = useCallback((block: AddressedBlock) => {
    setOverrides((prev) => {
      const next = new Map(prev);
      next.set(block.id, !(prev.get(block.id) ?? defaultCollapsed(block)));
      return next;
    });
  }, []);

  return { isCollapsed, toggle };
}
