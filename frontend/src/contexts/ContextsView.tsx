import { pageTitle, useDocumentTitle } from '../shared/useDocumentTitle';
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Link, Navigate, useLocation, useParams } from 'react-router-dom';
import { entityPath } from '../entities/navigation';
import type { EntityType } from '../entities/types';
import { RecordList } from '../search/components/SearchResults';
import ToleranceSlider from '../search/components/ToleranceSlider';
import { useSearch } from '../search/hooks/useSearch';
import { useTolerance } from '../search/hooks/useTolerance';
import type { RecordHit, SearchHit } from '../search/types';
import { recordDragProps, type DraggedRecord } from '../shared/recordDrag';
import { isoDate, isoDateTime } from '../shared/isoDate';
import { tokens } from '../shared/tokens';
import { usePolling } from '../shared/usePolling';
import { fetchContextPage, fetchContextTree, fetchInbox, fetchSessionRefs, quickCreate, type QuickCreateType } from './api';
import ContextTreeNav from './components/ContextTreeNav';
import { contextPaths } from './contextPaths';
import SessionFollowPicker from './components/SessionFollowPicker';
import type {
  ContextNode,
  ContextPage,
  ContextRef,
  FiledRecord,
  GoalItem,
  NoteItem,
  SessionRefs,
  TodoItem,
  TouchedRecord,
  WishlistItem,
} from './types';
import {
  InboxIdContext,
  useContextLink,
  useFollowedSession,
  useIncludeDescendants,
  useIncludeInactive,
} from './useContextLink';

const POLL_SECONDS = 15;
// While following a live session, everything polls this often so its work shows up as it happens.
const FOLLOW_POLL_SECONDS = 2;

// Types the context page lists in its own sections; any other search hit in scope goes
// under "Other matches".
const PAGE_TYPE_SECTIONS = [
  ['Goal', 'Goals'],
  ['Todo', 'Todos'],
  ['Note', 'Notes'],
  ['Wishlist', 'Wishlist'],
] as const;
const PAGE_TYPES = new Set<string>(PAGE_TYPE_SECTIONS.map(([type]) => type));

function pageRows(page: ContextPage, type: (typeof PAGE_TYPE_SECTIONS)[number][0]): { id: number }[] {
  return { Goal: page.goals, Todo: page.todos, Note: page.notes, Wishlist: page.wishlist }[type];
}

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
  const [includeInactive, setIncludeInactive] = useIncludeInactive();

  // Typing filters context names; Enter submits the text as a kb search. Editing the text
  // again drops the search, back to name filtering.
  const [filterText, setFilterText] = useState('');
  const [submittedQuery, setSubmittedQuery] = useState('');
  const tolerance = useTolerance();
  const {
    hits,
    resultsFor,
    loading: searching,
    error: searchError,
    refresh: refreshSearch,
  } = useSearch(submittedQuery, tolerance.settled);
  const search = submittedQuery ? { query: submittedQuery, hits, searching, error: searchError } : null;
  const changeFilter = (text: string) => {
    setFilterText(text);
    setSubmittedQuery('');
  };
  // Following a session narrows the page to the records it has touched; a search then
  // narrows further, to the touched records it matches.
  const [followedId, setFollowedId] = useFollowedSession();
  const [changesOnly, setChangesOnly] = useState(false);
  const fetchRefs = useCallback(
    () => (followedId === null ? Promise.resolve(null) : fetchSessionRefs(followedId)),
    [followedId],
  );
  const [refsLive, setRefsLive] = useState<boolean | null>(null);
  const pollSeconds = followedId !== null && refsLive !== false ? FOLLOW_POLL_SECONDS : POLL_SECONDS;
  const { data: refsData, error: refsError } = usePolling(fetchRefs, pollSeconds);
  const refs = followedId === null ? null : refsData;
  useEffect(() => setRefsLive(refs?.live ?? null), [refs?.live]);
  const followed = refs ? refs.records.filter((r) => r.changed || !changesOnly) : null;
  const followKeys = followed && new Set(followed.map((r) => hitKey(r.type, r.id)));
  const searchKeys = search && !search.error ? new Set(search.hits.map((h) => hitKey(h.type, h.id))) : null;
  const followedShown = followed && searchKeys ? followed.filter((r) => searchKeys.has(hitKey(r.type, r.id))) : followed;
  const searchShown = search && followKeys ? search.hits.filter((h) => followKeys.has(hitKey(h.type, h.id))) : search?.hits;
  // The records the page is narrowed to; null when neither filter is active.
  const filterHits: RecordHit[] | null = followedShown ?? (search ? search.hits : null);

  // While filtered, the page shows the filter's records in the selected context, or all of
  // them: on request, while following a session (its default), or on its own when a search
  // just run finds nothing here. Either stays until the user picks a context in the sidebar
  // or "only this context".
  const [showAllHits, setShowAllHits] = useState(followedId !== null);
  const autoShowAllPending = useRef(false);
  useEffect(() => setShowAllHits(followedId !== null), [submittedQuery, followedId]);
  const runSearch = () => {
    autoShowAllPending.current = true;
    setSubmittedQuery(filterText.trim());
  };

  const fetchTree = useCallback(() => fetchContextTree(), []);
  const { data: tree, error: treeError, refresh: refreshTree } = usePolling(fetchTree, pollSeconds);
  const fetchPage = useCallback(
    () =>
      selectedId === null ? Promise.resolve(null) : fetchContextPage(selectedId, includeDescendants, includeInactive),
    [selectedId, includeDescendants, includeInactive],
  );
  const { data: page, error: pageError, refresh: refreshPage } = usePolling(fetchPage, pollSeconds);
  useDocumentTitle(page && page.context.id === selectedId ? pageTitle('contexts', page.context.name) : null);
  // After a context or record moved: everything showing placements is stale.
  const refreshAll = () => {
    refreshTree();
    refreshPage();
    if (submittedQuery) refreshSearch();
  };

  // The page's scope (this context, plus descendants when included), to place filtered records in it.
  const scopeIds = useMemo(
    () => (selectedId === null || !tree ? new Set<number>() : scopeOf(tree, selectedId, includeDescendants)),
    [tree, selectedId, includeDescendants],
  );
  const contextNames = useMemo(() => new Map((tree ?? []).map((n) => [n.id, n.name])), [tree]);
  const hitsHere = filterHits ? filterHits.filter((h) => inScope(h, scopeIds)) : [];
  const shownTotal = filterHits?.length ?? 0;
  useEffect(() => {
    if (!autoShowAllPending.current || searching || resultsFor !== submittedQuery) return;
    autoShowAllPending.current = false;
    if (hitsHere.length === 0 && shownTotal > 0) setShowAllHits(true);
  }, [searching, resultsFor, submittedQuery, shownTotal, hitsHere.length]);

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
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
          }}
        >
          <SessionFollowPicker
            followedId={followedId}
            followedTitle={refs?.title ?? null}
            followedLive={refs?.live ?? null}
            onFollow={setFollowedId}
          />
          {treeError && <p style={{ color: tokens.color.danger, fontSize: 12 }}>{treeError}</p>}
          {tree && (
            <ContextTreeNav
              nodes={tree}
              selectedId={selectedId}
              includeDescendants={includeDescendants}
              onChanged={refreshAll}
              filterText={filterText}
              onFilterChange={changeFilter}
              onSearch={runSearch}
              onSelectContext={() => setShowAllHits(false)}
              recordHits={followedShown ?? (search && !search.error ? search.hits : null)}
            />
          )}
        </aside>
        <main style={{ flex: 1, minWidth: 0, overflowY: 'auto', padding: '16px 24px' }}>
          {followedId !== null && (
            <FollowBanner
              refs={refs}
              error={refsError}
              shown={showAllHits ? shownTotal : hitsHere.length}
              total={shownTotal}
              showAll={showAllHits}
              onShowAll={setShowAllHits}
              changesOnly={changesOnly}
              onChangesOnly={setChangesOnly}
              onStop={() => setFollowedId(null)}
            />
          )}
          {search && (
            <SearchBanner
              search={search}
              total={searchShown?.length ?? 0}
              shown={showAllHits ? (searchShown?.length ?? 0) : hitsHere.length}
              showAll={showAllHits}
              onShowAll={followedId === null ? setShowAllHits : null}
              onClear={() => changeFilter('')}
              tolerance={tolerance.value}
              onTolerance={tolerance.set}
            />
          )}
          {pageError && <p style={{ color: tokens.color.danger }}>{pageError}</p>}
          {filterHits && showAllHits ? (
            followedId !== null ? (
              <RecordsByType hits={filterHits} tree={tree ?? []} />
            ) : (
              <RecordList hits={filterHits} describe={describeRecord} />
            )
          ) : (
            page &&
            page.context.id === selectedId && (
              <ContextPageBody
                page={page}
                includeDescendants={includeDescendants}
                onIncludeDescendants={setIncludeDescendants}
                includeInactive={includeInactive}
                onIncludeInactive={setIncludeInactive}
                contextNames={contextNames}
                hits={filterHits ? hitsHere : null}
                textFilter={search ? '' : filterText}
                onCreated={refreshAll}
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

function inScope(hit: RecordHit, scopeIds: Set<number>): boolean {
  return hit.context_ids.some((c) => scopeIds.has(c));
}

const linkButton = { ...tokens.link, background: 'none', border: 'none', padding: 0, cursor: 'pointer' } as const;
const bannerStyle = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: 10,
  alignItems: 'center',
  fontSize: 13,
  marginBottom: 16,
  minHeight: 20,
} as const;

// A row's TYPE:ID line: how a search matched it, or what a followed session did to it.
function describeRecord(hit: RecordHit): string {
  if (isTouched(hit)) return `${hit.changed ? 'changed' : 'read'} ${isoDateTime(hit.last_at_utc)}`;
  if (isSearchHit(hit)) return hit.is_substring ? 'substring' : `dist=${hit.dist.toFixed(3)}`;
  return '';
}

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

const isTouched = (hit: RecordHit): hit is TouchedRecord => 'changed' in hit;
const isSearchHit = (hit: RecordHit): hit is SearchHit => 'dist' in hit;

function FollowBanner({
  refs,
  error,
  shown,
  total,
  showAll,
  onShowAll,
  changesOnly,
  onChangesOnly,
  onStop,
}: {
  refs: SessionRefs | null; // null until the first load
  error: string | null;
  shown: number;
  total: number;
  showAll: boolean;
  onShowAll: (value: boolean) => void;
  changesOnly: boolean;
  onChangesOnly: (value: boolean) => void;
  onStop: () => void;
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 16 }}>
      <div style={{ ...bannerStyle, marginBottom: 0 }}>
        {error ? (
          <span style={{ color: tokens.color.danger }}>{error}</span>
        ) : !refs ? (
          <span style={{ color: tokens.color.textMuted }}>Loading the session's records…</span>
        ) : (
          <span>
            {showAll ? plural(total, 'record') : `${shown} of ${plural(total, 'record')} here`} touched by{' '}
            <strong>{refs.title || 'untitled session'}</strong>
          </span>
        )}
        {refs && <Chip color={refs.live ? tokens.color.accent : undefined}>{refs.live ? 'live' : 'ended'}</Chip>}
        <button onClick={() => onShowAll(!showAll)} style={linkButton}>
          {showAll ? 'only this context' : 'show all'}
        </button>
        <label style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <input type="checkbox" checked={changesOnly} onChange={(e) => onChangesOnly(e.target.checked)} />
          changes only
        </label>
        <button onClick={onStop} style={linkButton}>
          stop following
        </button>
      </div>
      {refs && refs.si_nodes.length > 0 && (
        <p style={{ margin: 0, fontSize: 12, color: tokens.color.textMuted }}>
          si nodes read: {refs.si_nodes.map((n) => n.title).join(', ')}
        </p>
      )}
    </div>
  );
}

function SearchBanner({
  search,
  shown,
  total,
  showAll,
  onShowAll,
  onClear,
  tolerance,
  onTolerance,
}: {
  search: { query: string; hits: SearchHit[]; searching: boolean; error: string | null };
  shown: number;
  total: number; // matches the page can show: every hit, or those a followed session touched
  showAll: boolean;
  onShowAll: ((value: boolean) => void) | null; // null while FollowBanner owns the toggle
  onClear: () => void;
  tolerance: number | null;
  onTolerance: (value: number) => void;
}) {
  return (
    <div style={bannerStyle}>
      {search.error ? (
        <span style={{ color: tokens.color.danger }}>{search.error}</span>
      ) : search.searching && search.hits.length === 0 ? (
        <span style={{ color: tokens.color.textMuted }}>Searching kb for “{search.query}”…</span>
      ) : (
        <span>
          {showAll ? plural(total, 'match', 'matches') : `${shown} of ${plural(total, 'match', 'matches')} here`} for “{search.query}”
        </span>
      )}
      {onShowAll && (
        <button onClick={() => onShowAll(!showAll)} style={linkButton}>
          {showAll ? 'only this context' : 'show all'}
        </button>
      )}
      <button onClick={onClear} style={linkButton}>
        clear search
      </button>
      {tolerance !== null && <ToleranceSlider value={tolerance} onChange={onTolerance} />}
    </div>
  );
}

function ContextPageBody({
  page,
  includeDescendants,
  onIncludeDescendants,
  includeInactive,
  onIncludeInactive,
  contextNames,
  hits,
  textFilter,
  onCreated,
}: {
  page: ContextPage;
  includeDescendants: boolean;
  onIncludeDescendants: (v: boolean) => void;
  includeInactive: boolean;
  onIncludeInactive: (v: boolean) => void;
  contextNames: Map<number, string>;
  hits: RecordHit[] | null; // the filter's records in this page's scope; null when no filter is active
  textFilter: string; // typed in the sidebar box: rows whose title contains it
  onCreated: () => void;
}) {
  const contextLink = useContextLink();
  const hitKeys = hits && new Set(hits.map((h) => hitKey(h.type, h.id)));
  const needle = textFilter.trim().toLowerCase();
  const matchesRow = (type: string, id: number, title: string) =>
    (!hitKeys || hitKeys.has(hitKey(type, id))) && title.toLowerCase().includes(needle);
  const matches = (type: string) => (row: { id: number; title: string }) => matchesRow(type, row.id, row.title);
  const goals = page.goals.filter(matches('Goal'));
  const todos = page.todos.filter(matches('Todo'));
  const notes = page.notes.filter(matches('Note'));
  const wishlist = page.wishlist.filter(matches('Wishlist'));
  const others = page.others.filter((r) => matchesRow(r.type, r.id, r.label));
  const otherTypes = [...new Set(others.map((r) => r.type))];
  // Filter matches the page doesn't list in any of its sections.
  const pageKeys = new Set([
    ...PAGE_TYPE_SECTIONS.flatMap(([type]) => pageRows(page, type).map((r) => hitKey(type, r.id))),
    ...page.others.map((r) => hitKey(r.type, r.id)),
  ]);
  const otherHits = (hits ?? []).filter((h) => !pageKeys.has(hitKey(h.type, h.id)));

  const now = Date.now();
  const isScheduled = (t: TodoItem) => !t.inactive && t.defer_until_utc !== null && Date.parse(t.defer_until_utc) > now;
  // The server sends todos in triage order (Todo.triage_key).
  const open = todos.filter((t) => !isScheduled(t));
  const scheduled = todos
    .filter(isScheduled)
    .sort((a, b) => Date.parse(a.defer_until_utc!) - Date.parse(b.defer_until_utc!));
  const here = page.context.id;
  const quickAdd = (type: QuickCreateType) => ({
    type,
    submit: async (title: string) => {
      const created = await quickCreate(type, title, here);
      onCreated();
      return created.id;
    },
  });

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
          <label
            style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}
            title="Also list done/dropped todos, abandoned goals, inactive dailies, ..."
          >
            <input type="checkbox" checked={includeInactive} onChange={(e) => onIncludeInactive(e.target.checked)} />
            show inactive
          </label>
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

      <Section title="Goals" count={goals.length} add={quickAdd('Goal')}>
        {goals.map((g) => (
          <GoalRow key={g.id} goal={g} here={here} />
        ))}
      </Section>

      <Section title="Todos" count={open.length} add={quickAdd('Todo')}>
        {open.map((t) => (
          <TodoRow key={t.id} todo={t} here={here} />
        ))}
      </Section>

      <Section title="Scheduled" count={scheduled.length}>
        {scheduled.map((t) => (
          <TodoRow key={t.id} todo={t} here={here} showDeferDate />
        ))}
      </Section>

      <Section title="Notes" count={notes.length} add={quickAdd('Note')}>
        {notes.map((n) => (
          <NoteRow key={n.id} note={n} here={here} />
        ))}
      </Section>

      <Section title="Wishlist" count={wishlist.length} add={quickAdd('Wishlist')}>
        {wishlist.map((w) => (
          <WishlistRow key={w.id} item={w} here={here} />
        ))}
      </Section>

      {otherTypes.map((type) => {
        const rows = others.filter((r) => r.type === type);
        return (
          <Section key={type} title={type} count={rows.length}>
            {rows.map((r) => (
              <FiledRow key={r.id} record={r} here={here} contextNames={contextNames} />
            ))}
          </Section>
        );
      })}

      {hits && (
        <Section title="Other matches" count={otherHits.length}>
          <RecordList hits={otherHits} describe={describeRecord} />
        </Section>
      )}
    </div>
  );
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

interface QuickAdd {
  type: QuickCreateType;
  submit: (title: string) => Promise<number>; // resolves to the new record's id
}

function Section({
  title,
  count,
  add,
  children,
}: {
  title: string;
  count: number;
  add?: QuickAdd;
  children: ReactNode;
}) {
  const [adding, setAdding] = useState(false);
  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <h2 style={{ margin: '0 0 6px', fontSize: 14, fontWeight: 600, display: 'flex', alignItems: 'baseline', gap: 6 }}>
        {title} <span style={{ color: tokens.color.textMuted, fontWeight: 400 }}>{count}</span>
        {add && (
          <button
            onClick={() => setAdding(true)}
            title={`New ${add.type}`}
            aria-label={`New ${add.type}`}
            style={{ ...tokens.glyphButton, fontSize: 16 }}
          >
            +
          </button>
        )}
      </h2>
      {add && adding && <QuickAddInput add={add} onClose={() => setAdding(false)} />}
      {count === 0 && !adding ? (
        <p style={{ margin: 0, fontSize: 13, color: tokens.color.textMuted }}>none</p>
      ) : (
        children
      )}
    </section>
  );
}

// Stays open after each Enter, for adding several records in a row; Esc (or leaving it
// empty) closes it. The status beside the input names the record just added, since a new
// row can sort out of view.
function QuickAddInput({ add, onClose }: { add: QuickAdd; onClose: () => void }) {
  const [title, setTitle] = useState('');
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<{ addedId: number } | { error: string } | null>(null);
  const submit = async () => {
    setBusy(true);
    try {
      const id = await add.submit(title.trim());
      setTitle('');
      setStatus({ addedId: id });
    } catch (e) {
      setStatus({ error: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(false);
    }
  };
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4, fontSize: 12 }}>
      <input
        autoFocus
        value={title}
        readOnly={busy}
        placeholder={`new ${add.type.toLowerCase()} title, Enter to add, Esc to close`}
        onChange={(e) => setTitle(e.target.value)}
        onBlur={() => !busy && !title.trim() && onClose()}
        onKeyDown={(e) => {
          if (e.key === 'Escape') onClose();
          if (e.key === 'Enter' && title.trim() && !busy) submit();
        }}
        style={{ ...tokens.input, flex: 1, maxWidth: 560 }}
      />
      {status && 'error' in status && <span style={{ color: tokens.color.danger }}>{status.error}</span>}
      {status && 'addedId' in status && (
        <Link to={entityPath(add.type, status.addedId)} style={tokens.link}>
          added {add.type[0]}
          {status.addedId}
        </Link>
      )}
    </div>
  );
}

// Every row is a record that can be dragged onto a context in the sidebar to move it there.
// An inactive row (done, abandoned, ...; shown only on request) is dimmed, so current work still reads first.
function Row({ record, inactive, children }: { record: DraggedRecord; inactive?: boolean; children: ReactNode }) {
  return (
    <div
      {...recordDragProps(record)}
      style={{
        opacity: inactive ? 0.55 : 1,
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

function IdCell({ type, id }: { type: string; id: number }) {
  return (
    <span style={{ color: tokens.color.textMuted, width: 44, flexShrink: 0, fontVariantNumeric: 'tabular-nums' }}>
      {type[0]}
      {id}
    </span>
  );
}

function TitleLink({ type, id, title }: { type: EntityType; id: number; title: string }) {
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

function GoalRow({ goal, here }: { goal: GoalItem; here: number }) {
  return (
    <Row record={{ type: 'Goal', id: goal.id, label: goal.title }} inactive={goal.inactive}>
      <IdCell type="Goal" id={goal.id} />
      {goal.inactive && <Chip>{goal.status.replace('_', ' ')}</Chip>}
      <TitleLink type="Goal" id={goal.id} title={goal.title} />
      <Where context={goal.context} viaTag={goal.via_tag} here={here} />
    </Row>
  );
}

// A record of any other filed type (Event, Daily, Idea, ...), in its type's own section.
function FiledRow({ record, here, contextNames }: { record: FiledRecord; here: number; contextNames: Map<number, string> }) {
  // Several homes means it floats in on a tag; the page shows where only for a single other home.
  const home = record.context_ids.length === 1 ? record.context_ids[0] : null;
  const context = home === null ? null : { id: home, name: contextNames.get(home) ?? `#${home}` };
  return (
    <Row record={{ type: record.type, id: record.id, label: record.label }} inactive={record.inactive}>
      <IdCell type={record.type} id={record.id} />
      {record.inactive && <Chip>inactive</Chip>}
      {record.drilldown ? (
        <TitleLink type={record.type as EntityType} id={record.id} title={record.label} />
      ) : (
        <span style={{ minWidth: 0 }}>{record.label}</span>
      )}
      <Where context={context} viaTag={null} here={here} />
    </Row>
  );
}

function TodoRow({ todo, here, showDeferDate }: { todo: TodoItem; here: number; showDeferDate?: boolean }) {
  return (
    <Row record={{ type: 'Todo', id: todo.id, label: todo.title }} inactive={todo.inactive}>
      <IdCell type="Todo" id={todo.id} />
      {todo.inactive && <Chip>{todo.status.replace('_', ' ')}</Chip>}
      {showDeferDate && (
        <span style={{ color: tokens.color.due, whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums' }}>
          {isoDate(todo.defer_until_utc)}
        </span>
      )}
      {todo.urgent && <Chip color={tokens.color.danger}>urgent</Chip>}
      {todo.resolution_distance && <Chip>{todo.resolution_distance.replace('_', ' ')}</Chip>}
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
    <Row record={{ type: 'Wishlist', id: item.id, label: item.title }} inactive={item.inactive}>
      <IdCell type="Wishlist" id={item.id} />
      {item.inactive && <Chip>inactive</Chip>}
      {item.pinned && <Chip color={tokens.color.accent}>pinned</Chip>}
      <TitleLink type="Wishlist" id={item.id} title={item.title} />
      {price && <Chip>{price}</Chip>}
      {item.priority !== null && <Chip>priority {item.priority}</Chip>}
      <Where context={item.context} viaTag={null} here={here} />
    </Row>
  );
}

// Records grouped into the page's own sections, in its order, then one section per other
// type present; each section is sub-grouped by context.
function RecordsByType({ hits, tree }: { hits: RecordHit[]; tree: ContextNode[] }) {
  const paths = useMemo(() => contextPaths(tree), [tree]);
  const otherTypes = [...new Set(hits.map((h) => h.type).filter((t) => !PAGE_TYPES.has(t)))].sort();
  const sections: (readonly [string, string])[] = [...PAGE_TYPE_SECTIONS, ...otherTypes.map((t) => [t, t] as const)];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 960 }}>
      {sections.map(([type, title]) => (
        <TypeSection key={type} title={title} hits={hits.filter((h) => h.type === type)} paths={paths} />
      ))}
    </div>
  );
}

// The section's count is its records; a record in several contexts is one record shown under each.
function TypeSection({ title, hits, paths }: { title: string; hits: RecordHit[]; paths: ContextPath[] }) {
  return (
    <Section title={title} count={hits.length}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {groupByContext(hits, paths).map((group) => (
          <ContextGroup key={group.contextId ?? 'none'} group={group} />
        ))}
      </div>
    </Section>
  );
}

type ContextPath = ReturnType<typeof contextPaths>[number];

interface RecordGroup {
  contextId: number | null; // null: records with no (live) context
  path: string;
  hits: RecordHit[];
}

// One group per context holding any of the records, in tree order, each keeping the records'
// incoming order; a tag-addressed record lands under every context it lives in. Records in no
// known context come last.
function groupByContext(hits: RecordHit[], paths: ContextPath[]): RecordGroup[] {
  const groups = paths
    .map(({ id, path }) => ({ contextId: id, path, hits: hits.filter((h) => h.context_ids.includes(id)) }))
    .filter((g) => g.hits.length > 0);
  const known = new Set(paths.map((p) => p.id));
  const homeless = hits.filter((h) => !h.context_ids.some((c) => known.has(c)));
  return homeless.length > 0 ? [...groups, { contextId: null, path: 'no context', hits: homeless }] : groups;
}

function ContextGroup({ group }: { group: RecordGroup }) {
  const contextLink = useContextLink();
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <h3 style={{ margin: 0, fontSize: 12, fontWeight: 600, color: tokens.color.textMuted }}>
        {group.contextId === null ? (
          group.path
        ) : (
          <Link to={contextLink(group.contextId)} style={tokens.link}>
            {group.path}
          </Link>
        )}{' '}
        <span style={{ fontWeight: 400 }}>{group.hits.length}</span>
      </h3>
      <RecordList hits={group.hits} describe={describeRecord} />
    </div>
  );
}