import { pageTitle, useDocumentTitle } from '../shared/useDocumentTitle';
import { useState } from 'react';
import { tokens } from '../shared/tokens';
import SearchHelp from './components/SearchHelp';
import SearchInput from './components/SearchInput';
import SearchResults from './components/SearchResults';
import ToleranceSlider from './components/ToleranceSlider';
import { useSearch } from './hooks/useSearch';
import { useTolerance } from './hooks/useTolerance';

// Mirrors `kb search`: substring + semantic, ranked together. Search fires
// explicitly (Enter or the Search button), not on every keystroke.
export default function SearchView() {
  const [query, setQuery] = useState('');
  const [submittedQuery, setSubmittedQuery] = useState('');
  useDocumentTitle(pageTitle('search', submittedQuery || 'Search'));
  const tolerance = useTolerance();
  const { hits, loading, error } = useSearch(submittedQuery, tolerance.settled);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <h1 style={{ margin: 0, fontSize: 20 }}>Search</h1>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <div style={{ flex: 1 }}>
          <SearchInput value={query} onChange={setQuery} onSubmit={() => setSubmittedQuery(query)} />
        </div>
        <SearchHelp />
      </div>
      {tolerance.value !== null && <ToleranceSlider value={tolerance.value} onChange={tolerance.set} />}
      {/* One fixed-height status line, so results don't shift when a re-run starts or ends. */}
      <p style={{ margin: 0, minHeight: 18, fontSize: 13, color: error ? tokens.color.danger : tokens.color.textMuted }}>
        {error ?? (loading ? 'Searching...' : submittedQuery ? `${hits.length} matches` : '')}
      </p>
      {!error && <SearchResults hits={hits} />}
    </div>
  );
}
