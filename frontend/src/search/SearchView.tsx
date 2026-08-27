import { useState } from 'react';
import { tokens } from '../shared/tokens';
import SearchInput from './components/SearchInput';
import SearchResults from './components/SearchResults';
import { useDebouncedValue } from './hooks/useDebouncedValue';
import { useSearch } from './hooks/useSearch';

// Mirrors `kb search`: substring + semantic, ranked together. Query debounced so
// typing doesn't fire a request per keystroke.
export default function SearchView() {
  const [query, setQuery] = useState('');
  const debouncedQuery = useDebouncedValue(query, 300);
  const { hits, loading, error } = useSearch(debouncedQuery);

  return (
    <div style={{ maxWidth: 720, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 16 }}>
      <h1 style={{ margin: 0, fontSize: 20 }}>Search</h1>
      <SearchInput value={query} onChange={setQuery} />
      {loading && <p style={{ color: tokens.color.textMuted }}>Searching...</p>}
      {error && <p style={{ color: tokens.color.danger }}>{error}</p>}
      {!loading && !error && <SearchResults hits={hits} />}
    </div>
  );
}
