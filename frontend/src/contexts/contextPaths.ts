import type { ContextNode } from './types';

const SEPARATOR = ' / ';

// Every context as its full tree path ("pg / alice"), depth-first in name order.
export function contextPaths(nodes: ContextNode[]): { id: number; path: string }[] {
  const children = new Map<number | null, ContextNode[]>();
  for (const n of nodes) {
    const key = n.parent_id !== null && nodes.some((p) => p.id === n.parent_id) ? n.parent_id : null;
    children.set(key, [...(children.get(key) ?? []), n]);
  }
  const out: { id: number; path: string }[] = [];
  const walk = (parent: number | null, prefix: string) => {
    for (const n of [...(children.get(parent) ?? [])].sort((a, b) => a.name.localeCompare(b.name))) {
      const path = prefix + n.name;
      out.push({ id: n.id, path });
      walk(n.id, path + SEPARATOR);
    }
  };
  walk(null, '');
  return out;
}
