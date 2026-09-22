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

export function linkifyEntityRefs(root: HTMLElement): void {
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
        a.textContent = full;
        a.className = 'kb-entity-ref';
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
