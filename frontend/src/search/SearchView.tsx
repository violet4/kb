import { useState } from 'react';
import { tokens } from '../shared/tokens';
import SearchInput from './components/SearchInput';
import SearchResults from './components/SearchResults';
import { useSearch } from './hooks/useSearch';

// Mirrors `kb search`: substring + semantic, ranked together. Search fires
// explicitly (Enter or the Search button), not on every keystroke.
export default function SearchView() {
  const [query, setQuery] = useState('');
  const [submittedQuery, setSubmittedQuery] = useState('');
  const { hits, loading, error } = useSearch(submittedQuery);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <h1 style={{ margin: 0, fontSize: 20 }}>Search</h1>
      <SearchInput value={query} onChange={setQuery} onSubmit={() => setSubmittedQuery(query)} />
      {loading && <p style={{ color: tokens.color.textMuted }}>Searching...</p>}
      {error && <p style={{ color: tokens.color.danger }}>{error}</p>}
      {!loading && !error && <SearchResults hits={hits} />}
    </div>
  );
}
