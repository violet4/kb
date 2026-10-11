import { useCallback, type ReactNode } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { entityPath } from '../entities/navigation';
import { tokens } from '../shared/tokens';
import { usePolling } from '../shared/usePolling';
import { fetchContextPage, fetchContextTree } from './api';
import ContextTreeNav from './components/ContextTreeNav';
import type { ContextPage, ContextRef, NoteItem, TodoItem } from './types';

const POLL_SECONDS = 15;

export default function ContextsView() {
  const { id } = useParams();
  const selectedId = id !== undefined ? Number(id) : null;
  const [searchParams, setSearchParams] = useSearchParams();
  // Sub-context items are included unless ?sub=0 -- Redmine's default for subprojects too.
  const includeDescendants = searchParams.get('sub') !== '0';

  const { data: tree, error: treeError } = usePolling(fetchContextTree, POLL_SECONDS);
  const fetchPage = useCallback(
    () => (selectedId === null ? Promise.resolve(null) : fetchContextPage(selectedId, includeDescendants)),
    [selectedId, includeDescendants],
  );
  const { data: page, error: pageError } = usePolling(fetchPage, POLL_SECONDS);

  const setIncludeDescendants = (value: boolean) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.delete('sub');
    else next.set('sub', '0');
    setSearchParams(next, { replace: true });
  };

  return (
    <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
      <aside
        style={{
          width: 260,
          flexShrink: 0,
          overflowY: 'auto',
          padding: 16,
          borderRight: `1px solid ${tokens.color.border}`,
        }}
      >
        {treeError && <p style={{ color: tokens.color.danger, fontSize: 12 }}>{treeError}</p>}
        {tree && <ContextTreeNav nodes={tree} selectedId={selectedId} />}
      </aside>
      <main style={{ flex: 1, minWidth: 0, overflowY: 'auto', padding: '16px 24px' }}>
        {selectedId === null && <p style={{ color: tokens.color.textMuted }}>Pick a context.</p>}
        {pageError && <p style={{ color: tokens.color.danger }}>{pageError}</p>}
        {page && page.context.id === selectedId && (
          <ContextPageBody
            page={page}
            includeDescendants={includeDescendants}
            onIncludeDescendants={setIncludeDescendants}
          />
        )}
      </main>
    </div>
  );
}

function ContextPageBody({
  page,
  includeDescendants,
  onIncludeDescendants,
}: {
  page: ContextPage;
  includeDescendants: boolean;
  onIncludeDescendants: (v: boolean) => void;
}) {
  const now = Date.now();
  const isScheduled = (t: TodoItem) => t.defer_until_utc !== null && Date.parse(t.defer_until_utc) > now;
  const open = page.todos.filter((t) => !isScheduled(t)).sort(compareOpenTodos);
  const scheduled = page.todos
    .filter(isScheduled)
    .sort((a, b) => Date.parse(a.defer_until_utc!) - Date.parse(b.defer_until_utc!));
  const here = page.context.id;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 960 }}>
      <header style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <Breadcrumb ancestors={page.ancestors} />
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, flexWrap: 'wrap' }}>
          <h1 style={{ margin: 0, fontSize: 20 }}>{page.context.name}</h1>
          {page.tags.map((t) => (
            <Chip key={t}>{t}</Chip>
          ))}
          {page.children.length > 0 && (
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
              <input
                type="checkbox"
                checked={includeDescendants}
                onChange={(e) => onIncludeDescendants(e.target.checked)}
              />
              include sub-contexts
            </label>
          )}
        </div>
        {page.description && <p style={{ margin: 0, color: tokens.color.textMuted, fontSize: 13 }}>{page.description}</p>}
        {page.children.length > 0 && (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', fontSize: 13 }}>
            <span style={{ color: tokens.color.textMuted }}>sub-contexts:</span>
            {page.children.map((c) => (
              <Link key={c.id} to={`/contexts/${c.id}`} style={tokens.link}>
                {c.name}
              </Link>
            ))}
          </div>
        )}
      </header>

      <Section title="Goals" count={page.goals.length}>
        {page.goals.map((g) => (
          <Row key={g.id}>
            <IdCell type="Goal" id={g.id} />
            <TitleLink type="Goal" id={g.id} title={g.title} />
            <Where context={g.context} viaTag={g.via_tag} here={here} />
          </Row>
        ))}
      </Section>

      <Section title="Todos" count={open.length}>
        {open.map((t) => (
          <TodoRow key={t.id} todo={t} here={here} />
        ))}
      </Section>

      <Section title="Scheduled" count={scheduled.length}>
        {scheduled.map((t) => (
          <TodoRow key={t.id} todo={t} here={here} showDeferDate />
        ))}
      </Section>

      <Section title="Notes" count={page.notes.length}>
        {page.notes.map((n) => (
          <NoteRow key={n.id} note={n} here={here} />
        ))}
      </Section>
    </div>
  );
}

// Urgent first, then in-progress, then newest.
function compareOpenTodos(a: TodoItem, b: TodoItem): number {
  if (a.urgent !== b.urgent) return a.urgent ? -1 : 1;
  const ip = (t: TodoItem) => (t.status === 'in_progress' ? 0 : 1);
  if (ip(a) !== ip(b)) return ip(a) - ip(b);
  return b.id - a.id;
}

function isoDate(utc: string | null): string {
  if (!utc) return '';
  const d = new Date(utc);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function Breadcrumb({ ancestors }: { ancestors: ContextRef[] }) {
  if (ancestors.length === 0) return null;
  return (
    <div style={{ fontSize: 12, color: tokens.color.textMuted, display: 'flex', gap: 6 }}>
      {ancestors.map((a) => (
        <span key={a.id} style={{ display: 'flex', gap: 6 }}>
          <Link to={`/contexts/${a.id}`} style={tokens.link}>
            {a.name}
          </Link>
          <span>›</span>
        </span>
      ))}
    </div>
  );
}

function Section({ title, count, children }: { title: string; count: number; children: ReactNode }) {
  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <h2 style={{ margin: '0 0 6px', fontSize: 14, fontWeight: 600 }}>
        {title} <span style={{ color: tokens.color.textMuted, fontWeight: 400 }}>{count}</span>
      </h2>
      {count === 0 ? <p style={{ margin: 0, fontSize: 13, color: tokens.color.textMuted }}>none</p> : children}
    </section>
  );
}

function Row({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'baseline',
        gap: 8,
        padding: '4px 0',
        borderBottom: `1px solid ${tokens.color.border}`,
        fontSize: 13,
      }}
    >
      {children}
    </div>
  );
}

function IdCell({ type, id }: { type: 'Goal' | 'Todo' | 'Note'; id: number }) {
  return (
    <span style={{ color: tokens.color.textMuted, width: 44, flexShrink: 0, fontVariantNumeric: 'tabular-nums' }}>
      {type[0]}
      {id}
    </span>
  );
}

function TitleLink({ type, id, title }: { type: 'Goal' | 'Todo' | 'Note'; id: number; title: string }) {
  return (
    <Link to={entityPath(type, id)} style={{ ...tokens.link, minWidth: 0 }}>
      {title}
    </Link>
  );
}

function Chip({ children, color }: { children: ReactNode; color?: string }) {
  return (
    <span
      style={{
        fontSize: 11,
        padding: '0 6px',
        borderRadius: 8,
        border: `1px solid ${color ?? tokens.color.border}`,
        color: color ?? tokens.color.textMuted,
        whiteSpace: 'nowrap',
      }}
    >
      {children}
    </span>
  );
}

// Shown only when the row lives somewhere other than the page's own context: a
// sub-context it was filed under, or the tag it floats in on.
function Where({ context, viaTag, here }: { context: ContextRef | null; viaTag: string | null; here: number }) {
  if (viaTag) return <Chip>#{viaTag}</Chip>;
  if (!context || context.id === here) return null;
  return (
    <Link to={`/contexts/${context.id}`} style={{ ...tokens.link, fontSize: 11, whiteSpace: 'nowrap' }}>
      @{context.name}
    </Link>
  );
}

function TodoRow({ todo, here, showDeferDate }: { todo: TodoItem; here: number; showDeferDate?: boolean }) {
  return (
    <Row>
      <IdCell type="Todo" id={todo.id} />
      {showDeferDate && (
        <span style={{ color: tokens.color.due, whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums' }}>
          {isoDate(todo.defer_until_utc)}
        </span>
      )}
      {todo.urgent && <Chip color={tokens.color.danger}>urgent</Chip>}
      {todo.kind !== 'task' && <Chip color={todo.kind === 'bug' ? tokens.color.danger : undefined}>{todo.kind}</Chip>}
      {todo.status === 'in_progress' && <Chip color={tokens.color.accent}>in progress</Chip>}
      <TitleLink type="Todo" id={todo.id} title={todo.title} />
      {todo.effort && <Chip>{todo.effort}</Chip>}
      {todo.severity && <Chip>{todo.severity}</Chip>}
      {todo.goal && (
        <Link to={entityPath('Goal', todo.goal.id)} style={{ ...tokens.link, fontSize: 11, whiteSpace: 'nowrap' }}>
          G{todo.goal.id}
        </Link>
      )}
      <Where context={todo.context} viaTag={todo.via_tag} here={here} />
    </Row>
  );
}

function NoteRow({ note, here }: { note: NoteItem; here: number }) {
  return (
    <Row>
      <IdCell type="Note" id={note.id} />
      <TitleLink type="Note" id={note.id} title={note.title} />
      <Chip>{note.collection}</Chip>
      <Where context={note.context} viaTag={null} here={here} />
      <span style={{ color: tokens.color.textMuted, fontSize: 11, whiteSpace: 'nowrap' }}>
        {isoDate(note.updated_at_utc)}
      </span>
    </Row>
  );
}
