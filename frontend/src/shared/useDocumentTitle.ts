import { useEffect } from 'react';

// Each page's tab-title prefix. An icon instead of a word, since a narrow tab truncates from
// the end and the page's own name (a context, a session) is what tells tabs apart.
export const PAGE_ICON = {
  contexts: '🗂️',
  agents: '🤖',
  search: '🔍',
  browse: '🗄️',
  dailies: '🔁',
  events: '📅',
  log: '📝',
  channels: '💬',
} as const;

const DEFAULT_TITLE = 'kb';

// Sets the browser tab's title while the calling page is mounted. null (e.g. while the page's
// data is still loading) leaves the default.
export function useDocumentTitle(title: string | null): void {
  useEffect(() => {
    document.title = title ?? DEFAULT_TITLE;
    return () => {
      document.title = DEFAULT_TITLE;
    };
  }, [title]);
}

export function pageTitle(page: keyof typeof PAGE_ICON, name: string): string {
  return `${PAGE_ICON[page]} ${name}`;
}
