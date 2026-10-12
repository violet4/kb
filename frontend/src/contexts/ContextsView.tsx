import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { Link, Navigate, useLocation, useParams } from 'react-router-dom';
import { entityPath } from '../entities/navigation';
import SearchResults from '../search/components/SearchResults';
import { useSearch } from '../search/hooks/useSearch';
import type { SearchHit } from '../search/types';
import { recordDragProps, type DraggedRecord } from '../shared/recordDrag';
import { tokens } from '../shared/tokens';
import { usePolling } from '../shared/usePolling';
import { fetchContextPage, fetchContextTree, fetchInbox } from './api';
import ContextTreeNav from './components/ContextTreeNav';
import type { ContextNode, ContextPage, ContextRef, NoteItem, TodoItem, WishlistItem } from './types';
import { InboxIdContext, useContextLink, useIncludeDescendants } from './useContextLink';

const POLL_SECONDS = 15;

// Types the context page lists in its own sections; any other search hit in scope goes
// under "Other matches".
const PAGE_TYPES = new Set(['Goal', 'Todo', 'Note', 'Wishlist']);

const hitKey = (type: string, id: number) => `${type}:${id}`;

export default function ContextsView() {
  const { id } = useParams();
  const location = useLocation();
  const [inboxId, setInboxId] = useState<number | null>(null);
  useEffect(() => {
    fetchInbox().then((inbox) => setInboxId(inbox.id));
  }, []);
  // Bare /contexts is the inbox.
  const selectedId = id !== undefined ? Number(id) : inboxId;
  const [includeDescendants, setIncludeDescendants] = useIncludeDescendants();

  // Typing filters context names; Enter submits the text as a kb search. Editing the text
  // again drops the search, back to name filtering.
  const [filterText, setFilterText] = useState('');
  const [submittedQuery, setSubmittedQuery] = useState('');
  const { hits, loading: searching, error: searchError, refresh: refreshSearch } = useSearch(submittedQuery);
  const search = submittedQuery ? { query: submittedQuery, hits, searching, error: searchError } : null;
  const changeFilter = (text: string) => {
    setFilterText(text);
    setSubmittedQuery('');
  };
  // During a search the page shows the selected context's matches, or every match on request.
  const [showAllHits, setShowAllHits] = useState(false);
  useEffect(() => setShowAllHits(false), [selectedId, submittedQuery]);

  const { data: tree, error: treeError, refresh: refreshTree } = usePolling(fetchContextTree, POLL_SECONDS);
  const fetchPage = useCallback(
    () => (selectedId === null ? Promise.resolve(null) : fetchContextPage(selectedId, includeDescendants)),
    [selectedId, includeDescendants],
  );
  const { data: page, error: pageError, refresh: refreshPage } = usePolling(fetchPage, POLL_SECONDS);
  // After a context or record moved: everything showing placements is stale.
  const refreshAll = () => {
    refreshTree();
    refreshPage();
    if (submittedQuery) refreshSearch();
  };

  // The page's scope (this context, plus descendants when included), to place search hits in it.
  const scopeIds = useMemo(
    () => (selectedId === null || !tree ? new Set<number>() : scopeOf(tree, selectedId, includeDescendants)),
    [tree, selectedId, includeDescendants],
  );
  const hitsHere = search ? search.hits.filter((h) => inScope(h, scopeIds)) : [];

  if (id !== undefined && inboxId !== null && Number(id) === inboxId) {
    return <Navigate to={`/contexts${location.search}`} replace />;
  }

  return (
    <InboxIdContext.Provider value={inboxId}>
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
          {tree && (
            <ContextTreeNav
              nodes={tree}
              selectedId={selectedId}
              includeDescendants={includeDescendants}
              onChanged={refreshAll}
              filterText={filterText}
              onFilterChange={changeFilter}
              onSearch={() => setSubmittedQuery(filterText.trim())}
              searchHits={search && !search.error ? search.hits : null}
            />
          )}
        </aside>
        <main style={{ flex: 1, minWidth: 0, overflowY: 'auto', padding: '16px 24px' }}>
          {search && (
            <SearchBanner
              search={search}
              shown={showAllHits ? search.hits.length : hitsHere.length}
              showAll={showAllHits}
              onShowAll={setShowAllHits}
              onClear={() => changeFilter('')}
            />
          )}
          {pageError && <p style={{ color: tokens.color.danger }}>{pageError}</p>}
          {search && showAllHits ? (
            <SearchResults hits={search.hits} />
          ) : (
            page &&
            page.context.id === selectedId && (
              <ContextPageBody
                page={page}
                includeDescendants={includeDescendants}
                onIncludeDescendants={setIncludeDescendants}
                hits={search ? hitsHere : null}
              />
            )
          )}
        </main>
      </div>
    </InboxIdContext.Provider>
  );
}

function scopeOf(tree: ContextNode[], rootId: number, includeDescendants: boolean): Set<number> {
  const scope = new Set([rootId]);
  if (!includeDescendants) return scope;
  let grew = true;
  while (grew) {
    grew = false;
    for (const n of tree) {
      if (n.parent_id !== null && scope.has(n.parent_id) && !scope.has(n.id)) {
        scope.add(n.id);
        grew = true;
      }
    }
  }
  return scope;
}

function inScope(hit: SearchHit, scopeIds: Set<number>): boolean {
  return hit.context_ids.some((c) => scopeIds.has(c));
}

function SearchBanner({
  search,
  shown,
  showAll,
  onShowAll,
  onClear,
}: {
  search: { query: string; hits: SearchHit[]; searching: boolean; error: string | null };
  shown: number;
  showAll: boolean;
  onShowAll: (value: boolean) => void;
  onClear: () => void;
}) {
  const linkButton = { ...tokens.link, background: 'none', border: 'none', padding: 0, cursor: 'pointer' };
  return (
    <div style={{ display: 'flex', gap: 10, alignItems: 'baseline', fontSize: 13, marginBottom: 16, minHeight: 20 }}>
      {search.error ? (
        <span style={{ color: tokens.color.danger }}>{search.error}</span>
      ) : search.searching && search.hits.length === 0 ? (
        <span style={{ color: tokens.color.textMuted }}>Searching kb for “{search.query}”…</span>
      ) : (
        <span>
          {showAll ? `${search.hits.length} matches` : `${shown} of ${search.hits.length} matches here`} for “
          {search.query}”
        </span>
      )}
      <button onClick={() => onShowAll(!showAll)} style={linkButton}>
        {showAll ? 'only this context' : 'show all'}
      </button>
      <button onClick={onClear} style={linkButton}>
        clear search
      </button>
    </div>
  );
}

function ContextPageBody({
  page,
  includeDescendants,
  onIncludeDescendants,
  hits,
}: {
  page: ContextPage;
  includeDescendants: boolean;
  onIncludeDescendants: (v: boolean) => void;
  hits: SearchHit[] | null; // search hits in this page's scope; null when no search is active
}) {
  const contextLink = useContextLink();
  const hitKeys = hits && new Set(hits.map((h) => hitKey(h.type, h.id)));
  const matches = (type: string) => (row: { id: number }) => !hitKeys || hitKeys.has(hitKey(type, row.id));
  const goals = page.goals.filter(matches('Goal'));
  const todos = page.todos.filter(matches('Todo'));
  const notes = page.notes.filter(matches('Note'));
  const wishlist = page.wishlist.filter(matches('Wishlist'));
  const otherHits = (hits ?? []).filter((h) => !PAGE_TYPES.has(h.type));

  const now = Date.now();
  const isScheduled = (t: TodoItem) => t.defer_until_utc !== null && Date.parse(t.defer_until_utc) > now;
  const open = todos.filter((t) => !isScheduled(t)).sort(compareOpenTodos);
  const scheduled = todos
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
              <Link key={c.id} to={contextLink(c.id)} style={tokens.link}>
                {c.name}
              </Link>
            ))}
          </div>
        )}
      </header>

      <Section title="Goals" count={goals.length}>
        {goals.map((g) => (
          <Row key={g.id} record={{ type: 'Goal', id: g.id, label: g.title }}>
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

      <Section title="Notes" count={notes.length}>
        {notes.map((n) => (
          <NoteRow key={n.id} note={n} here={here} />
        ))}
      </Section>

      <Section title="Wishlist" count={wishlist.length}>
        {wishlist.map((w) => (
          <WishlistRow key={w.id} item={w} here={here} />
        ))}
      </Section>

      {hits && (
        <Section title="Other matches" count={otherHits.length}>
          <SearchResults hits={otherHits} />
        </Section>
      )}
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
  const contextLink = useContextLink();
  if (ancestors.length === 0) return null;
  return (
    <div style={{ fontSize: 12, color: tokens.color.textMuted, display: 'flex', gap: 6 }}>
      {ancestors.map((a) => (
        <span key={a.id} style={{ display: 'flex', gap: 6 }}>
          <Link to={contextLink(a.id)} style={tokens.link}>
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

// Every row is a record that can be dragged onto a context in the sidebar to move it there.
function Row({ record, children }: { record: DraggedRecord; children: ReactNode }) {
  return (
    <div
      {...recordDragProps(record)}
      style={{
        cursor: 'grab',
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

function IdCell({ type, id }: { type: 'Goal' | 'Todo' | 'Note' | 'Wishlist'; id: number }) {
  return (
    <span style={{ color: tokens.color.textMuted, width: 44, flexShrink: 0, fontVariantNumeric: 'tabular-nums' }}>
      {type[0]}
      {id}
    </span>
  );
}

function TitleLink({ type, id, title }: { type: 'Goal' | 'Todo' | 'Note' | 'Wishlist'; id: number; title: string }) {
  return (
    <Link to={entityPath(type, id)} draggable={false} style={{ ...tokens.link, minWidth: 0 }}>
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
  const contextLink = useContextLink();
  if (viaTag) return <Chip>#{viaTag}</Chip>;
  if (!context || context.id === here) return null;
  return (
    <Link to={contextLink(context.id)} style={{ ...tokens.link, fontSize: 11, whiteSpace: 'nowrap' }}>
      @{context.name}
    </Link>
  );
}

function TodoRow({ todo, here, showDeferDate }: { todo: TodoItem; here: number; showDeferDate?: boolean }) {
  return (
    <Row record={{ type: 'Todo', id: todo.id, label: todo.title }}>
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
    <Row record={{ type: 'Note', id: note.id, label: note.title }}>
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

function priceRange(item: WishlistItem): string | null {
  const { price_min: lo, price_max: hi } = item;
  if (lo === null && hi === null) return null;
  if (lo !== null && hi !== null && lo !== hi) return `$${lo}–$${hi}`;
  return `$${lo ?? hi}`;
}

function WishlistRow({ item, here }: { item: WishlistItem; here: number }) {
  const price = priceRange(item);
  return (
    <Row record={{ type: 'Wishlist', id: item.id, label: item.title }}>
      <IdCell type="Wishlist" id={item.id} />
      {item.pinned && <Chip color={tokens.color.accent}>pinned</Chip>}
      <TitleLink type="Wishlist" id={item.id} title={item.title} />
      {price && <Chip>{price}</Chip>}
      {item.priority !== null && <Chip>priority {item.priority}</Chip>}
      <Where context={item.context} viaTag={null} here={here} />
    </Row>
  );
}
