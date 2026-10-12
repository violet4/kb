import { useEffect, useMemo, useRef, useState } from 'react';
import { tokens } from '../../shared/tokens';
import { fetchContextTree, fetchTags } from '../api';
import type { ContextNode, ContextRef, Placement, PlacementChoice } from '../types';

interface Option {
  key: string;
  label: string;
  depth: number;
  choice: PlacementChoice;
  current: boolean;
  match: boolean; // false for an ancestor shown only to keep a match placed in the hierarchy
}

// Contexts in tree order (children alphabetical under their parent), each with its depth.
function flattenTree(nodes: ContextNode[]): { node: ContextNode; depth: number; ancestors: number[] }[] {
  const ids = new Set(nodes.map((n) => n.id));
  const childrenOf = new Map<number | null, ContextNode[]>();
  for (const n of nodes) {
    const parent = n.parent_id !== null && ids.has(n.parent_id) ? n.parent_id : null;
    if (!childrenOf.has(parent)) childrenOf.set(parent, []);
    childrenOf.get(parent)!.push(n);
  }
  const result: { node: ContextNode; depth: number; ancestors: number[] }[] = [];
  const walk = (parent: number | null, depth: number, ancestors: number[]) => {
    for (const n of childrenOf.get(parent) ?? []) {
      result.push({ node: n, depth, ancestors });
      walk(n.id, depth + 1, [...ancestors, n.id]);
    }
  };
  walk(null, 0, []);
  return result;
}

// Type-to-filter over the full context hierarchy (indented, matches keep their ancestors),
// plus tags when the record may float on one. Arrow keys move, Enter picks, Esc cancels.
export default function ContextPicker({
  value,
  nullable,
  onPick,
  onCancel,
}: {
  value: Placement;
  nullable: boolean;
  onPick: (choice: PlacementChoice) => void;
  onCancel: () => void;
}) {
  const [tree, setTree] = useState<ContextNode[] | null>(null);
  const [tags, setTags] = useState<ContextRef[]>([]);
  const [filter, setFilter] = useState('');
  const [active, setActive] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchContextTree().then(setTree);
    if (value.tag_allowed) fetchTags().then(setTags);
  }, [value.tag_allowed]);

  const options = useMemo(() => {
    if (!tree) return [];
    const needle = filter.trim().toLowerCase().replace(/^[#@]/, '');
    const flat = flattenTree(tree);
    const matchIds = new Set(flat.filter((f) => f.node.name.toLowerCase().includes(needle)).map((f) => f.node.id));
    const keep = new Set([...matchIds, ...flat.filter((f) => matchIds.has(f.node.id)).flatMap((f) => f.ancestors)]);
    const result: Option[] = [];
    if (nullable && !needle) {
      result.push({ key: 'none', label: '(none)', depth: 0, choice: {}, current: !value.context && !value.tag, match: true });
    }
    for (const f of flat) {
      if (!keep.has(f.node.id)) continue;
      result.push({
        key: `c${f.node.id}`,
        label: f.node.name,
        depth: f.depth,
        choice: { context_id: f.node.id },
        current: value.context?.id === f.node.id,
        match: matchIds.has(f.node.id),
      });
    }
    for (const t of tags) {
      if (!t.name.toLowerCase().includes(needle)) continue;
      result.push({
        key: `t${t.id}`,
        label: `#${t.name}`,
        depth: 0,
        choice: { tag_id: t.id },
        current: value.tag?.id === t.id,
        match: true,
      });
    }
    return result;
  }, [tree, tags, filter, nullable, value]);

  // Start on the first real match while filtering, else on the current placement.
  useEffect(() => {
    const index = filter ? options.findIndex((o) => o.match) : options.findIndex((o) => o.current);
    setActive(Math.max(index, 0));
  }, [filter, options]);

  useEffect(() => {
    listRef.current?.querySelector(`[data-index="${active}"]`)?.scrollIntoView({ block: 'nearest' });
  }, [active]);

  const firstTag = options.findIndex((o) => o.key.startsWith('t'));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, width: 280 }}>
      <input
        autoFocus
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        placeholder={value.tag_allowed ? 'filter contexts and #tags' : 'filter contexts'}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') setActive((i) => Math.min(i + 1, options.length - 1));
          else if (e.key === 'ArrowUp') setActive((i) => Math.max(i - 1, 0));
          else if (e.key === 'Enter' && options[active]) onPick(options[active].choice);
          else if (e.key === 'Escape') onCancel();
          else return;
          e.preventDefault();
        }}
        style={{
          background: tokens.color.background,
          color: tokens.color.text,
          border: `1px solid ${tokens.color.border}`,
          borderRadius: 4,
          padding: '4px 8px',
          fontSize: 13,
        }}
      />
      <div ref={listRef} role="listbox" style={{ maxHeight: 320, overflowY: 'auto', fontSize: 13 }}>
        {!tree && <div style={{ color: tokens.color.textMuted }}>loading…</div>}
        {tree && options.length === 0 && <div style={{ color: tokens.color.textMuted }}>no match</div>}
        {options.map((o, i) => (
          <div key={o.key}>
            {i === firstTag && (
              <div style={{ color: tokens.color.textMuted, fontSize: 11, margin: '6px 0 2px' }}>tags</div>
            )}
            <div
              data-index={i}
              role="option"
              aria-selected={o.current}
              onMouseEnter={() => setActive(i)}
              onMouseDown={(e) => e.preventDefault()} // keep focus in the filter input
              onClick={() => onPick(o.choice)}
              style={{
                padding: '2px 6px',
                paddingLeft: 6 + o.depth * 14,
                borderRadius: 3,
                cursor: 'pointer',
                background: i === active ? tokens.color.border : 'transparent',
                color: o.match ? tokens.color.text : tokens.color.textMuted,
                fontWeight: o.current ? 600 : 400,
              }}
            >
              {o.label}
              {o.current && <span style={{ color: tokens.color.accent }}> ✓</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
