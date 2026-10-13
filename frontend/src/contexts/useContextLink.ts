import { createContext, useContext } from 'react';
import { useSearchParams } from 'react-router-dom';

// Page settings kept in the query string. Every link to a context page goes through
// useContextLink, so they carry over as you move around the tree.
const CARRIED_PARAMS = ['sub', 'session'] as const;

function useQueryParam(name: (typeof CARRIED_PARAMS)[number]): [string | null, (value: string | null) => void] {
  const [searchParams, setSearchParams] = useSearchParams();
  const set = (value: string | null) => {
    const next = new URLSearchParams(searchParams);
    if (value === null) next.delete(name);
    else next.set(name, value);
    setSearchParams(next, { replace: true });
  };
  return [searchParams.get(name), set];
}

// ?sub=1 turns on "include sub-contexts" (off by default).
export function useIncludeDescendants(): [boolean, (value: boolean) => void] {
  const [value, set] = useQueryParam('sub');
  return [value === '1', (on) => set(on ? '1' : null)];
}

// ?session=<harness session id> follows that agent session: the page shows only the records
// it has touched.
export function useFollowedSession(): [string | null, (harnessId: string | null) => void] {
  return useQueryParam('session');
}

// The inbox context's id. Inbox is the Contexts page's home: it lives at bare /contexts,
// and /contexts/<inbox id> redirects there. Outside the Contexts page (no provider) links
// use the id form and that redirect canonicalizes them.
export const InboxIdContext = createContext<number | null>(null);

export function useContextLink(): (id: number) => string {
  const [searchParams] = useSearchParams();
  const inboxId = useContext(InboxIdContext);
  const carried = new URLSearchParams();
  for (const name of CARRIED_PARAMS) {
    const value = searchParams.get(name);
    if (value !== null) carried.set(name, value);
  }
  const query = carried.size > 0 ? `?${carried}` : '';
  return (id) => `/contexts${id === inboxId ? '' : `/${id}`}${query}`;
}
