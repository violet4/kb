import { useEffect, useMemo, useRef } from 'react';
import DOMPurify from 'dompurify';
import { marked } from 'marked';
import { useNavigate } from 'react-router-dom';
import { tokens } from './tokens';
import { linkifyEntityRefs } from '../entities/linkifyEntityRefs';

const codeStyle = `
  .kb-markdown :is(h1, h2, h3, h4, h5, h6) { margin: 0.6em 0 0.3em; }
  .kb-markdown p, .kb-markdown ul, .kb-markdown ol { margin: 0.4em 0; }
  .kb-markdown ul, .kb-markdown ol { padding-left: 1.4em; }
  .kb-markdown code { font-family: monospace; font-size: 0.9em; background: ${tokens.color.background}; padding: 0.1em 0.3em; border-radius: 3px; }
  .kb-markdown pre { background: ${tokens.color.background}; border: 1px solid ${tokens.color.border}; border-radius: 6px; padding: 8px 10px; overflow-x: auto; }
  .kb-markdown pre code { background: none; padding: 0; }
  .kb-markdown a { color: ${tokens.link.color}; text-decoration: ${tokens.link.textDecoration}; }
  .kb-markdown blockquote { margin: 0.4em 0; padding-left: 0.8em; border-left: 3px solid ${tokens.color.border}; color: ${tokens.color.textMuted}; }
`;

let styleInjected = false;
function ensureStyleInjected() {
  if (styleInjected) return;
  const style = document.createElement('style');
  style.textContent = codeStyle;
  document.head.appendChild(style);
  styleInjected = true;
}

interface MarkdownProps {
  text: string;
}

// Adapter around marked+dompurify (see kb Notes #285/#286 for the supply-chain audit) --
// keeps the two libraries confined to this one component per kb instructions #39
// (libraries), so callers (SessionTranscript, etc.) never touch marked/dompurify directly.
export default function Markdown({ text }: MarkdownProps) {
  ensureStyleInjected();
  const html = useMemo(() => DOMPurify.sanitize(marked.parse(text, { async: false, breaks: true })), [text]);
  // dangerouslySetInnerHTML must receive a referentially stable object across renders where
  // `html` itself hasn't changed -- a fresh `{ __html: html }` literal every render (even
  // with the same string inside it) makes React re-set innerHTML on every unrelated
  // re-render (a sibling's state change, a parent re-render), which silently reverts
  // linkifyEntityRefs's DOM edits below without the below useEffect re-firing to redo them
  // (its own dependency, `html`, didn't change) -- confirmed live: an entity-ref link would
  // flash in on mount, then vanish on the next unrelated re-render.
  const htmlProp = useMemo(() => ({ __html: html }), [html]);
  const ref = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  // Runs post-sanitize, on the real DOM -- a Type:ID reference (e.g. "Todo:102") is not
  // markdown syntax, so this is a plain text-node walk/replace rather than a marked
  // extension; kept as a separate pass (not folded into the html memo above) so it
  // re-links after every render without re-running marked/DOMPurify.
  useEffect(() => {
    if (ref.current) linkifyEntityRefs(ref.current);
  }, [html]);
  // linkifyEntityRefs emits plain <a href> (dangerouslySetInnerHTML can't produce a real
  // <Link>), so a click is intercepted here and routed through the SPA router instead of
  // letting the browser do a full page navigation/reload.
  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const anchor = (e.target as HTMLElement).closest('a.kb-entity-ref') as HTMLAnchorElement | null;
    if (!anchor) return;
    e.preventDefault();
    navigate(anchor.getAttribute('href') ?? '/');
  };
  return (
    <div
      ref={ref}
      className="kb-markdown"
      style={{ fontSize: 14, color: tokens.color.text }}
      onClick={handleClick}
      dangerouslySetInnerHTML={htmlProp}
    />
  );
}
