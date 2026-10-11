import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { tokens } from '../../shared/tokens';
import type { ContextNode } from '../types';

interface TreeIndex {
  byId: Map<number, ContextNode>;
  childrenOf: Map<number | null, ContextNode[]>;
  subtreeTotal: Map<number, number>;
}

function buildIndex(nodes: ContextNode[]): TreeIndex {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const childrenOf = new Map<number | null, ContextNode[]>();
  for (const n of nodes) {
    const parent = n.parent_id !== null && byId.has(n.parent_id) ? n.parent_id : null;
    if (!childrenOf.has(parent)) childrenOf.set(parent, []);
    childrenOf.get(parent)!.push(n);
  }
  const subtreeTotal = new Map<number, number>();
  const total = (n: ContextNode): number => {
    const own = n.counts.todos + n.counts.goals + n.counts.notes + n.counts.wishlist;
    const sum = own + (childrenOf.get(n.id) ?? []).reduce((acc, c) => acc + total(c), 0);
    subtreeTotal.set(n.id, sum);
    return sum;
  };
  for (const root of childrenOf.get(null) ?? []) total(root);
  return { byId, childrenOf, subtreeTotal };
}

function ancestorIds(index: TreeIndex, id: number): number[] {
  const result: number[] = [];
  let node = index.byId.get(id);
  while (node && node.parent_id !== null) {
    result.push(node.parent_id);
    node = index.byId.get(node.parent_id);
  }
  return result;
}

export default function ContextTreeNav({ nodes, selectedId }: { nodes: ContextNode[]; selectedId: number | null }) {
  const index = useMemo(() => buildIndex(nodes), [nodes]);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [filter, setFilter] = useState('');
  const [hideEmpty, setHideEmpty] = useState(true);

  // Reveal the selected context: expand it and its ancestors whenever the selection changes.
  useEffect(() => {
    if (selectedId === null) return;
    setExpanded((prev) => new Set([...prev, selectedId, ...ancestorIds(index, selectedId)]));
  }, [selectedId, index]);

  const needle = filter.trim().toLowerCase();
  // With a filter, show every match plus its ancestors (so it stays placed in the tree).
  const filterVisible = useMemo(() => {
    if (!needle) return null;
    const visible = new Set<number>();
    for (const n of nodes) {
      if (n.name.toLowerCase().includes(needle)) {
        visible.add(n.id);
        for (const a of ancestorIds(index, n.id)) visible.add(a);
      }
    }
    return visible;
  }, [needle, nodes, index]);

  const isShown = (n: ContextNode) => {
    if (filterVisible) return filterVisible.has(n.id);
    if (hideEmpty && (index.subtreeTotal.get(n.id) ?? 0) === 0 && n.id !== selectedId) return false;
    return true;
  };

  const toggle = (id: number) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const renderLevel = (parent: number | null, depth: number) =>
    (index.childrenOf.get(parent) ?? []).filter(isShown).map((n) => {
      const kids = (index.childrenOf.get(n.id) ?? []).filter(isShown);
      const open = filterVisible !== null || expanded.has(n.id);
      const total = index.subtreeTotal.get(n.id) ?? 0;
      const selected = n.id === selectedId;
      return (
        <div key={n.id}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              paddingLeft: depth * 14,
              borderRadius: 4,
              background: selected ? tokens.color.surface : 'transparent',
            }}
          >
            <button
              onClick={() => toggle(n.id)}
              disabled={kids.length === 0}
              aria-label={open ? 'collapse' : 'expand'}
              style={{
                width: 16,
                padding: 0,
                border: 'none',
                background: 'none',
                color: tokens.color.textMuted,
                cursor: kids.length ? 'pointer' : 'default',
                visibility: kids.length ? 'visible' : 'hidden',
                fontSize: 10,
              }}
            >
              {open ? '▼' : '▶'}
            </button>
            <Link
              to={`/contexts/${n.id}`}
              style={{
                ...tokens.link,
                color: selected ? tokens.color.text : tokens.color.accent,
                fontWeight: selected ? 600 : 400,
                padding: '3px 0',
                fontSize: 13,
              }}
            >
              {n.name}
            </Link>
            {total > 0 && <span style={{ color: tokens.color.textMuted, fontSize: 11 }}>{total}</span>}
          </div>
          {open && kids.length > 0 && renderLevel(n.id, depth + 1)}
        </div>
      );
    });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <input
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        placeholder="filter contexts"
        style={{
          background: tokens.color.surface,
          color: tokens.color.text,
          border: `1px solid ${tokens.color.border}`,
          borderRadius: 4,
          padding: '4px 8px',
          fontSize: 13,
        }}
      />
      <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: tokens.color.textMuted }}>
        <input type="checkbox" checked={hideEmpty} onChange={(e) => setHideEmpty(e.target.checked)} />
        hide empty
      </label>
      <div>{renderLevel(null, 0)}</div>
    </div>
  );
}
