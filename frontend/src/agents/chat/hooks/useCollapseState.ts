import { useCallback, useMemo, useState } from 'react';
import type { AddressedBlock } from '../blockAddress';

interface UseCollapseStateResult {
  isCollapsed: (id: string) => boolean;
  toggle: (id: string) => void;
  collapseMatching: (blocks: AddressedBlock[]) => void;
  expandMatching: (blocks: AddressedBlock[]) => void;
}

// Collapsed-by-default rule: any block kind other than plain text starts collapsed (tool
// calls/results and any future unrecognized block kind), since those are usually the bulky,
// skim-later part of a transcript -- text is always the part worth reading immediately.
function defaultCollapsed(block: AddressedBlock): boolean {
  return block.block.kind !== 'text';
}

export function useCollapseState(allBlocks: AddressedBlock[]): UseCollapseStateResult {
  const defaults = useMemo(() => {
    const map = new Map<string, boolean>();
    for (const block of allBlocks) map.set(block.id, defaultCollapsed(block));
    return map;
  }, [allBlocks]);

  const [overrides, setOverrides] = useState<Map<string, boolean>>(new Map());

  const isCollapsed = useCallback(
    (id: string) => overrides.get(id) ?? defaults.get(id) ?? false,
    [overrides, defaults],
  );

  const toggle = useCallback((id: string) => {
    setOverrides((prev) => {
      const next = new Map(prev);
      next.set(id, !(prev.get(id) ?? defaults.get(id) ?? false));
      return next;
    });
    // defaults is stable enough per-render for this toggle's purposes -- omitted from deps
    // to avoid recreating the callback on every facet recompute.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const collapseMatching = useCallback((blocks: AddressedBlock[]) => {
    setOverrides((prev) => {
      const next = new Map(prev);
      for (const block of blocks) next.set(block.id, true);
      return next;
    });
  }, []);

  const expandMatching = useCallback((blocks: AddressedBlock[]) => {
    setOverrides((prev) => {
      const next = new Map(prev);
      for (const block of blocks) next.set(block.id, false);
      return next;
    });
  }, []);

  return { isCollapsed, toggle, collapseMatching, expandMatching };
}
