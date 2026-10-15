import type { KeyboardEvent } from 'react';

// Ctrl+Enter (Cmd+Enter on macOS) submits a multi-line text field, where plain Enter has to stay
// a newline. One definition so every long-form input answers to the same keys.
export function isSubmitShortcut(e: KeyboardEvent): boolean {
  return e.key === 'Enter' && (e.ctrlKey || e.metaKey);
}
