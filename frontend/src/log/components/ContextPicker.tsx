import { useMemo, useState } from 'react';
import { contextPaths } from '../../contexts/contextPaths';
import type { ContextNode } from '../../contexts/types';
import { tokens } from '../../shared/tokens';

interface Props {
  nodes: ContextNode[];
  selectedId: number | null;
  onChange: (id: number | null) => void;
}

// <input list> rather than <select>: with ~100+ contexts, substring search beats scrolling, and
// matching full paths means any ancestor name finds a context as well as its own name.
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
