import { useEffect, useState } from 'react';

// `value`, once it has stopped changing for `ms` -- e.g. to re-run a query only when a
// slider comes to rest rather than on every intermediate position.
export function useDebounced<T>(value: T, ms: number): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setSettled(value), ms);
    return () => window.clearTimeout(id);
  }, [value, ms]);
  return settled;
}
