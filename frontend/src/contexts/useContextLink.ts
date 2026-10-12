import { createContext, useContext } from 'react';
import { useSearchParams } from 'react-router-dom';

// ?sub=1 turns on "include sub-contexts" (off by default). Every link to a context page
// goes through useContextLink, so the setting carries over as you move around the tree.
export function useIncludeDescendants(): [boolean, (value: boolean) => void] {
  const [searchParams, setSearchParams] = useSearchParams();
  const set = (value: boolean) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set('sub', '1');
    else next.delete('sub');
    setSearchParams(next, { replace: true });
  };
  return [searchParams.get('sub') === '1', set];
}

// The inbox context's id. Inbox is the Contexts page's home: it lives at bare /contexts,
// and /contexts/<inbox id> redirects there. Outside the Contexts page (no provider) links
// use the id form and that redirect canonicalizes them.
export const InboxIdContext = createContext<number | null>(null);

export function useContextLink(): (id: number) => string {
  const [includeDescendants] = useIncludeDescendants();
  const inboxId = useContext(InboxIdContext);
  return (id) => `/contexts${id === inboxId ? '' : `/${id}`}${includeDescendants ? '?sub=1' : ''}`;
}
