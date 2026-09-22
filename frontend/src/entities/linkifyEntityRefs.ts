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

const REF_RE = /\b([A-Z][A-Za-z]*):(\d+)\b/g;

// Mirrors models.py's HasAutoLinks _entity_ref_re -- the same TYPE:ID grammar `kb link
// add` already accepts, detected here for display only (linking, not auto-link creation,
// which is the backend's job on write).
export function linkifyEntityRefs(root: HTMLElement): void {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      const parent = node.parentElement;
      // Don't relink inside an existing <a> (avoid nested anchors) or inside code/pre,
      // where a Type:ID-shaped string is likely literal text, not a real reference.
      if (parent && parent.closest('a, code, pre')) return NodeFilter.FILTER_REJECT;
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
      const [full, type, idStr] = match;
      if (match.index > lastIndex) frag.appendChild(document.createTextNode(text.slice(lastIndex, match.index)));
      if (KNOWN_TYPES.has(type as EntityType)) {
        const a = document.createElement('a');
        a.href = entityPath(type as EntityType, Number(idStr));
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
