import { entityPath } from './navigation';
import type { EntityType } from './types';

// Kept in sync with types.ts's EntityType union by hand (there is no runtime source of
// truth on the frontend the way entity_registry() is on the backend) -- an unlisted type
// (e.g. a ref to a table with no browsable entity page) is left as plain text rather than
// linked to a route that doesn't exist.
const KNOWN_TYPES = new Set<EntityType>([
  'Todo',
  'Goal',
  'Note',
  'Idea',
  'Wishlist',
  'Instruction',
  'Daily',
  'ArchivedLink',
  'LogEntry',
]);

// Short display-prefix -> real type aliases -- kept in sync with models.py's
// _ENTITY_REF_ALIASES by hand, same caveat as KNOWN_TYPES above.
const REF_ALIASES: Record<string, EntityType> = { AB: 'ArchivedLink' };

// Mirrors models.py's _entity_ref_re/_parse_entity_refs: every prose spelling of an entity
// reference actually in use across kb, not just the TYPE:ID form `kb link add` takes --
// "Note #343"/"Goal #14" (kb's own CLI output, and this assistant's own prose) are as real
// as "Note:343", and "AB23" is ArchivedLink's own established display-prefix spelling (no
// separator, no type name). Detected here for display only (linking, not auto-link
// creation, which is the backend's job on write) -- this can safely go stale relative to
// the backend's parser without breaking anything, only under-linking until synced.
const REF_RE = /\b([A-Z][A-Za-z]*)\s?#(\d+)\b|\b([A-Z][A-Za-z]*):(\d+)\b|\bAB(\d+)\b/g;

function parseMatch(match: RegExpExecArray): { type: EntityType; id: number } | null {
  const [, typeA, idA, typeB, idB, abId] = match;
  if (abId !== undefined) return { type: 'ArchivedLink', id: Number(abId) };
  const rawType = typeA ?? typeB;
  const rawId = idA ?? idB;
  const type = REF_ALIASES[rawType] ?? (rawType as EntityType);
  return KNOWN_TYPES.has(type) ? { type, id: Number(rawId) } : null;
}

export function labelKey(type: string, id: number): string {
  return `${type}:${id}`;
}

// Every distinct known-type ref in raw text, for callers that need to batch-fetch labels
// before the DOM exists to walk (see Markdown.tsx) -- shares REF_RE/parseMatch with the
// DOM-walking pass below so the two can never disagree on what counts as a ref.
export function extractEntityRefs(text: string): { type: EntityType; id: number }[] {
  const refs = new Map<string, { type: EntityType; id: number }>();
  REF_RE.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = REF_RE.exec(text))) {
    const ref = parseMatch(match);
    if (ref) refs.set(labelKey(ref.type, ref.id), ref);
  }
  return [...refs.values()];
}

// labels: resolved title text keyed by labelKey(type, id) (see entities/api.ts's
// resolveEntityLabels) -- when present for a ref, the link displays the resolved title
// instead of the raw "Note:413" text, with the raw text kept as the `title` attribute
// (a native hover tooltip, no extra component needed). Absent from the map (not yet
// fetched, or unresolved) falls back to the raw text, same as before this param existed.
export function linkifyEntityRefs(root: HTMLElement, labels?: Map<string, string>): void {
  // Anchors this function already created on an earlier pass (e.g. before labels had
  // resolved) -- their text is fixed once created, so when `labels` gains an entry for one
  // of these after the fact, update its display text/tooltip in place rather than leaving
  // it stuck at whatever the first pass rendered (the tree walker below deliberately never
  // revisits text inside an existing <a>, so without this pass a link created before labels
  // arrived would never pick up the resolved title).
  for (const a of root.querySelectorAll<HTMLAnchorElement>('a.kb-entity-ref[data-ref]')) {
    const full = a.dataset.ref ?? '';
    const key = a.dataset.refKey ?? '';
    const label = labels?.get(key);
    const wanted = label ?? full;
    if (a.textContent !== wanted) a.textContent = wanted;
    if (label) a.title = full;
    else a.removeAttribute('title');
  }

  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      const parent = node.parentElement;
      // Don't relink inside an existing <a> (avoid nested anchors) or inside code/pre,
      // where a ref-shaped string is likely literal text (a code sample, a log line), not
      // a real reference.
      if (parent && parent.closest('a, code, pre')) return NodeFilter.FILTER_REJECT;
      REF_RE.lastIndex = 0;
      return REF_RE.test(node.textContent ?? '') ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
    },
  });

  const targets: Text[] = [];
  let node: Node | null;
  // eslint-disable-next-line no-cond-assign
  while ((node = walker.nextNode())) targets.push(node as Text);

  for (const textNode of targets) {
    const text = textNode.textContent ?? '';
    REF_RE.lastIndex = 0;
    const frag = document.createDocumentFragment();
    let lastIndex = 0;
    let match: RegExpExecArray | null;
    while ((match = REF_RE.exec(text))) {
      const full = match[0];
      const ref = parseMatch(match);
      if (match.index > lastIndex) frag.appendChild(document.createTextNode(text.slice(lastIndex, match.index)));
      if (ref) {
        const a = document.createElement('a');
        a.href = entityPath(ref.type, ref.id);
        const key = labelKey(ref.type, ref.id);
        const label = labels?.get(key);
        a.textContent = label ?? full;
        if (label) a.title = full;
        a.className = 'kb-entity-ref';
        a.dataset.ref = full;
        a.dataset.refKey = key;
        frag.appendChild(a);
      } else {
        frag.appendChild(document.createTextNode(full));
      }
      lastIndex = match.index + full.length;
    }
    if (lastIndex < text.length) frag.appendChild(document.createTextNode(text.slice(lastIndex)));
    textNode.replaceWith(frag);
  }
}
