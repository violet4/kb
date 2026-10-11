import { useMemo, useState } from 'react';
import type { ContextNode } from '../../contexts/types';
import { tokens } from '../../shared/tokens';

const SEPARATOR = ' / ';

// Every context as its full tree path ("pg / alice"), depth-first in name order, so the
// native datalist's substring filter matches on any ancestor name as well as the leaf.
function contextPaths(nodes: ContextNode[]): { id: number; path: string }[] {
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

interface Props {
  nodes: ContextNode[];
  selectedId: number | null;
  onChange: (id: number | null) => void;
}

// <input list> rather than <select>: with ~100+ contexts, substring search beats scrolling.
// The text is local state; the parent only ever sees a resolved context id (or null while
// the typed text matches no path).
export default function ContextPicker({ nodes, selectedId, onChange }: Props) {
  const paths = useMemo(() => contextPaths(nodes), [nodes]);
  const selectedPath = paths.find((p) => p.id === selectedId)?.path ?? '';
  const [text, setText] = useState<string | null>(null); // null = mirror the selection

  const value = text ?? selectedPath;
  const invalid = text !== null && !paths.some((p) => p.path === text);

  return (
    <>
      <input
        list="log-context-paths"
        value={value}
        aria-label="Context"
        aria-invalid={invalid}
        placeholder="context"
        onFocus={(e) => e.currentTarget.select()}
        onChange={(e) => {
          const next = e.target.value;
          setText(next);
          const match = paths.find((p) => p.path === next);
          onChange(match ? match.id : null);
        }}
        onBlur={() => {
          if (!invalid) setText(null);
        }}
        style={{
          width: 260,
          background: tokens.color.surface,
          color: tokens.color.text,
          border: `1px solid ${invalid ? tokens.color.danger : tokens.color.border}`,
          borderRadius: 4,
          padding: '6px 8px',
          fontSize: 13,
        }}
      />
      <datalist id="log-context-paths">
        {paths.map((p) => (
          <option key={p.id} value={p.path} />
        ))}
      </datalist>
    </>
  );
}
