import { useEffect, useMemo, useRef, useState, type DragEvent, type MouseEvent } from 'react';
import { Link } from 'react-router-dom';
import SearchHelp from '../../search/components/SearchHelp';
import type { SearchHit } from '../../search/types';
import { tokens } from '../../shared/tokens';
import { draggedRecord, isRecordDrag, isRecordDragEvent, type DraggedRecord } from '../../shared/recordDrag';
import { createContext, moveContext, setPlacement } from '../api';
import type { ContextNode } from '../types';
import { useContextLink } from '../useContextLink';

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

function subtreeIds(index: TreeIndex, id: number): number[] {
  const result = [id];
  for (const child of index.childrenOf.get(id) ?? []) result.push(...subtreeIds(index, child.id));
  return result;
}

// Per-node count of search hits in its subtree; a tag-addressed hit living in several
// contexts counts once on each node above any of them.
function hitTotals(index: TreeIndex, hits: SearchHit[]): Map<number, number> {
  const totals = new Map<number, number>();
  for (const hit of hits) {
    const nodes = new Set(hit.context_ids.flatMap((cid) => [cid, ...ancestorIds(index, cid)]));
    for (const id of nodes) totals.set(id, (totals.get(id) ?? 0) + 1);
  }
  return totals;
}

// A drop target is the parent the dragged context would move under; ROOT means top level.
const ROOT = 'root' as const;
type DropTarget = number | typeof ROOT;

// Hovering a collapsed node this long while dragging expands it, so deep targets are reachable.
const HOVER_EXPAND_MS = 600;

export default function ContextTreeNav({
  nodes,
  selectedId,
  includeDescendants,
  onChanged,
  filterText,
  onFilterChange,
  onSearch,
  onSelectContext,
  searchHits,
}: {
  nodes: ContextNode[];
  selectedId: number | null;
  includeDescendants: boolean; // when false, counts are per node rather than per subtree
  onChanged: () => void;
  filterText: string;
  onFilterChange: (text: string) => void;
  onSearch: () => void;
  onSelectContext: () => void; // a context's link was clicked (even the one already selected)
  searchHits: SearchHit[] | null; // results of the submitted search; null when none is active
}) {
  const index = useMemo(() => buildIndex(nodes), [nodes]);
  const contextLink = useContextLink();
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [hideEmpty, setHideEmpty] = useState(true);
  // Contexts created in this session stay visible under "hide empty" although they hold nothing yet.
  const [justCreated, setJustCreated] = useState<Set<number>>(new Set());
  // Where an inline "new context" input is open: under a parent id, or ROOT; null when closed.
  const [creatingUnder, setCreatingUnder] = useState<DropTarget | null>(null);
  const [draggingId, setDraggingId] = useState<number | null>(null);
  const [dropTarget, setDropTarget] = useState<DropTarget | null>(null);
  const [error, setError] = useState<string | null>(null);
  const hoverExpandTimer = useRef<number | null>(null);

  // While a record is dragged from the page, every context is a drop target: the tree
  // shows in full (no search/name filter, no hide-empty) until the drag ends.
  const [recordDragging, setRecordDragging] = useState(false);
  useEffect(() => {
    const start = (e: globalThis.DragEvent) => setRecordDragging(isRecordDragEvent(e));
    const end = () => setRecordDragging(false);
    window.addEventListener('dragstart', start);
    window.addEventListener('dragend', end);
    window.addEventListener('drop', end);
    return () => {
      window.removeEventListener('dragstart', start);
      window.removeEventListener('dragend', end);
      window.removeEventListener('drop', end);
    };
  }, []);

  // Keep the selected context reachable: expand its ancestors (not the context itself).
  useEffect(() => {
    if (selectedId === null) return;
    setExpanded((prev) => new Set([...prev, ...ancestorIds(index, selectedId)]));
  }, [selectedId, index]);

  const searchTotals = useMemo(() => (searchHits ? hitTotals(index, searchHits) : null), [index, searchHits]);
  const needle = filterText.trim().toLowerCase();
  // A search shows contexts holding hits; otherwise a filter shows name matches. Either way,
  // ancestors stay so each match keeps its place in the tree, and everything shown is open.
  const filterVisible = useMemo(() => {
    // The selected context stays too, so the user can click back to it.
    if (searchTotals) {
      const selected = selectedId === null ? [] : [selectedId, ...ancestorIds(index, selectedId)];
      return new Set([...searchTotals.keys(), ...selected]);
    }
    if (!needle) return null;
    const visible = new Set<number>();
    for (const n of nodes) {
      if (n.name.toLowerCase().includes(needle)) {
        visible.add(n.id);
        for (const a of ancestorIds(index, n.id)) visible.add(a);
      }
    }
    return visible;
  }, [searchTotals, needle, nodes, index, selectedId]);

  // Shown outside a record drag: by the search/name filter, else by hide-empty.
  const isNormallyShown = (n: ContextNode) => {
    if (filterVisible) return filterVisible.has(n.id);
    const empty = (index.subtreeTotal.get(n.id) ?? 0) === 0;
    return !hideEmpty || !empty || n.id === selectedId || n.id === creatingUnder || justCreated.has(n.id);
  };
  const isShown = (n: ContextNode) => recordDragging || isNormallyShown(n);

  // Ctrl-click collapses or expands the whole subtree, following the clicked node's new state.
  const toggle = (id: number, e: MouseEvent) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      const open = !prev.has(id);
      for (const target of e.ctrlKey ? subtreeIds(index, id) : [id]) {
        if (open) next.add(target);
        else next.delete(target);
      }
      return next;
    });

  const run = async (action: () => Promise<void>) => {
    try {
      await action();
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const submitCreate = (name: string) => {
    const parentId = creatingUnder === ROOT || creatingUnder === null ? null : creatingUnder;
    return run(async () => {
      const created = await createContext(name, parentId);
      setJustCreated((prev) => new Set([...prev, created.id]));
      setCreatingUnder(null);
      onChanged();
    });
  };

  const startCreate = (under: DropTarget) => {
    setCreatingUnder(under);
    setError(null);
  };

  // A move is valid unless it targets the moved node itself, one of its descendants, or its current parent.
  const canMove = (movedId: number, target: DropTarget): boolean => {
    const moved = index.byId.get(movedId);
    if (!moved) return false;
    if (target === ROOT) return moved.parent_id !== null;
    return target !== movedId && target !== moved.parent_id && !ancestorIds(index, target).includes(movedId);
  };
  const canDrop = (target: DropTarget) => draggingId !== null && canMove(draggingId, target);

  const clearHoverTimer = () => {
    if (hoverExpandTimer.current !== null) window.clearTimeout(hoverExpandTimer.current);
    hoverExpandTimer.current = null;
  };

  const endDrag = () => {
    clearHoverTimer();
    setDraggingId(null);
    setDropTarget(null);
  };

  const dropHandlers = (target: DropTarget) => ({
    onDragOver: (e: DragEvent) => {
      // A dragged record can go on any context (not the top-level strip); whether a dragged
      // Context hit can move there is only knowable at drop time, when its payload is readable.
      const accepts = isRecordDrag(e) ? target !== ROOT : canDrop(target);
      if (!accepts) return;
      e.preventDefault(); // marks this element as a valid drop target
      e.dataTransfer.dropEffect = 'move';
      if (dropTarget !== target) {
        setDropTarget(target);
        clearHoverTimer();
        if (target !== ROOT && !expanded.has(target)) {
          hoverExpandTimer.current = window.setTimeout(
            () => setExpanded((prev) => new Set([...prev, target])),
            HOVER_EXPAND_MS,
          );
        }
      }
    },
    onDragLeave: (e: DragEvent) => {
      // Ignore leave events fired when moving between the row's own child elements.
      if (e.currentTarget.contains(e.relatedTarget as Node | null)) return;
      if (dropTarget === target) {
        setDropTarget(null);
        clearHoverTimer();
      }
    },
    onDrop: (e: DragEvent) => {
      e.preventDefault();
      const record = draggedRecord(e);
      if (record && target !== ROOT) {
        endDrag();
        dropRecord(record, target);
        return;
      }
      const movedId = draggingId;
      endDrag();
      if (movedId === null || !canMove(movedId, target)) return;
      run(async () => {
        await moveContext(movedId, target === ROOT ? null : target);
        onChanged();
      });
    },
  });

  // A record dropped on a context moves there; a Context search hit is re-parented instead.
  const dropRecord = (record: DraggedRecord, contextId: number) => {
    if (record.type === 'Context' && !canMove(record.id, contextId)) {
      setError(`can't move ${record.label} there`);
      return;
    }
    run(async () => {
      if (record.type === 'Context') await moveContext(record.id, contextId);
      else await setPlacement(record.type, record.id, { context_id: contextId });
      onChanged();
    });
  };

  // With sub-contexts excluded, a count is what's filed directly on the node, matching the page.
  // With sub-contexts excluded, an open node counts what's filed directly on it, matching
  // the page; a collapsed node with children counts its whole subtree (shown in parentheses),
  // so collapsing never hides that there is something inside.
  const displayCount = (n: ContextNode, collapsedWithKids: boolean): { count: number; rolledUp: boolean } => {
    const subtree = includeDescendants || collapsedWithKids;
    if (searchHits) {
      const count = subtree
        ? (searchTotals?.get(n.id) ?? 0)
        : searchHits.filter((h) => h.context_ids.includes(n.id)).length;
      return { count, rolledUp: subtree && !includeDescendants };
    }
    if (subtree) return { count: index.subtreeTotal.get(n.id) ?? 0, rolledUp: !includeDescendants };
    return { count: n.counts.todos + n.counts.goals + n.counts.notes + n.counts.wishlist, rolledUp: false };
  };

  const renderLevel = (parent: number | null, depth: number) =>
    (index.childrenOf.get(parent) ?? []).filter(isShown).map((n) => {
      const kids = (index.childrenOf.get(n.id) ?? []).filter(isShown);
      const creatingHere = creatingUnder === n.id;
      // A drag keeps every row that was already open open, so visible targets stay put.
      const open = (filterVisible?.has(n.id) ?? false) || expanded.has(n.id);
      const revealed = recordDragging && !isNormallyShown(n); // shown only for this drag
      const { count: total, rolledUp } = displayCount(n, !open && kids.length > 0);
      const selected = n.id === selectedId;
      const isDropTarget = dropTarget === n.id;
      return (
        <div key={n.id}>
          <div
            className="context-row"
            draggable
            onDragStart={(e) => {
              e.dataTransfer.effectAllowed = 'move';
              e.dataTransfer.setData('text/plain', n.name);
              setDraggingId(n.id);
            }}
            onDragEnd={endDrag}
            {...dropHandlers(n.id)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              paddingLeft: depth * 14,
              borderRadius: 4,
              background: isDropTarget
                ? tokens.color.border
                : selected
                  ? tokens.color.surface
                  : revealed
                    ? tokens.color.revealed
                    : 'transparent',
              outline: isDropTarget ? `1px solid ${tokens.color.accent}` : 'none',
              opacity: draggingId === n.id ? 0.5 : 1,
              cursor: 'grab',
            }}
          >
            <button
              onClick={(e) => toggle(n.id, e)}
              disabled={kids.length === 0}
              aria-label={open ? 'collapse' : 'expand'}
              title="Ctrl-click: collapse/expand everything below"
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
              to={contextLink(n.id)}
              onClick={onSelectContext}
              draggable={false}
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
            {total > 0 && (
              <span
                style={{ color: tokens.color.textMuted, fontSize: 11 }}
                title={rolledUp ? 'Includes sub-contexts; expand for per-context counts' : undefined}
              >
                {rolledUp ? `(${total})` : total}
              </span>
            )}
            <button
              className="context-row-add"
              onClick={() => startCreate(n.id)}
              title={`New context under ${n.name}`}
              aria-label={`New context under ${n.name}`}
              style={addButtonStyle}
            >
              +
            </button>
          </div>
          {creatingHere && (
            <div style={{ paddingLeft: (depth + 1) * 14 + 20 }}>
              <NewContextInput onSubmit={submitCreate} onCancel={() => setCreatingUnder(null)} />
            </div>
          )}
          {open && kids.length > 0 && renderLevel(n.id, depth + 1)}
        </div>
      );
    });

  const rootDropActive = draggingId !== null && canDrop(ROOT);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {/* Show the row's "+" only on hover/focus (inline styles have no :hover). Opacity, not
          visibility, so it stays keyboard-focusable and in the accessibility tree. */}
      <style>{`
        .context-row .context-row-add { opacity: 0; }
        .context-row:hover .context-row-add, .context-row-add:focus-visible { opacity: 1; }
      `}</style>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        <input
          value={filterText}
          onChange={(e) => onFilterChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && filterText.trim()) onSearch();
            if (e.key === 'Escape') onFilterChange('');
          }}
          placeholder="filter contexts or search kb"
          style={{ ...inputStyle, flex: 1, minWidth: 0 }}
        />
        <SearchHelp
          align="start"
          intro="Typing filters context names. Enter runs kb search, narrowing the tree and the page to the matching records; Esc clears."
        />
        <button
          onClick={() => startCreate(ROOT)}
          title="New top-level context"
          aria-label="New top-level context"
          style={{ ...addButtonStyle, fontSize: 16, padding: '0 6px' }}
        >
          +
        </button>
      </div>
      <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: tokens.color.textMuted }}>
        <input type="checkbox" checked={hideEmpty} onChange={(e) => setHideEmpty(e.target.checked)} />
        hide empty
      </label>
      {/* One slot reserved up front, so the top-level drop strip (while dragging) or the last
          error (otherwise) never shifts the tree. */}
      <div
        {...dropHandlers(ROOT)}
        style={{
          minHeight: 22,
          display: 'flex',
          alignItems: 'center',
          justifyContent: rootDropActive ? 'center' : 'flex-start',
          fontSize: rootDropActive ? 11 : 12,
          borderRadius: 4,
          border: `1px dashed ${rootDropActive ? tokens.color.accent : 'transparent'}`,
          background: dropTarget === ROOT ? tokens.color.border : 'transparent',
          color: rootDropActive ? tokens.color.textMuted : tokens.color.danger,
        }}
      >
        {rootDropActive ? 'drop here to move to top level' : error}
      </div>
      <div>
        {creatingUnder === ROOT && (
          <div style={{ paddingLeft: 20 }}>
            <NewContextInput onSubmit={submitCreate} onCancel={() => setCreatingUnder(null)} />
          </div>
        )}
        {renderLevel(null, 0)}
      </div>
    </div>
  );
}

function NewContextInput({ onSubmit, onCancel }: { onSubmit: (name: string) => Promise<void>; onCancel: () => void }) {
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  return (
    <input
      autoFocus
      value={name}
      disabled={busy}
      placeholder="new context name, Enter to create"
      onChange={(e) => setName(e.target.value)}
      onBlur={() => !busy && !name.trim() && onCancel()}
      onKeyDown={async (e) => {
        if (e.key === 'Escape') onCancel();
        if (e.key === 'Enter' && name.trim()) {
          setBusy(true);
          await onSubmit(name.trim());
          setBusy(false);
        }
      }}
      style={{ ...inputStyle, width: '100%', boxSizing: 'border-box', margin: '2px 0' }}
    />
  );
}

const inputStyle = {
  background: tokens.color.surface,
  color: tokens.color.text,
  border: `1px solid ${tokens.color.border}`,
  borderRadius: 4,
  padding: '4px 8px',
  fontSize: 13,
} as const;

const addButtonStyle = {
  padding: '0 4px',
  border: 'none',
  background: 'none',
  color: tokens.color.textMuted,
  cursor: 'pointer',
  fontSize: 13,
  lineHeight: 1,
} as const;
