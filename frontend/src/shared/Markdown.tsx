import { useMemo } from 'react';
import DOMPurify from 'dompurify';
import { marked } from 'marked';
import { tokens } from './tokens';

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
  return <div className="kb-markdown" style={{ fontSize: 14, color: tokens.color.text }} dangerouslySetInnerHTML={{ __html: html }} />;
}
