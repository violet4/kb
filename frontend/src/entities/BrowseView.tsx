import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { tokens } from '../shared/tokens';
import AvailableColumns from './components/AvailableColumns';
import EntityTable from './components/EntityTable';
import EntityTypeTabs from './components/EntityTypeTabs';
import GenericFilters from './components/GenericFilters';
import { useColumns } from './hooks/useColumns';
import { useEntityList } from './hooks/useEntityList';
import type { EntityType } from './types';

const TABS = ['Todo', 'Bugs', 'Goal', 'Note', 'Idea', 'Wishlist'] as const;
type Tab = (typeof TABS)[number];

// "Bugs" isn't a real entity type -- it's Todo with kind=bug (same table/lifecycle
// as Todo, see CLAUDE.md) -- so its tab resolves to Todo's own type + a fixed extra
// filter rather than being a separate entry in ENTITY_TYPES.
function resolveTab(tab: Tab): { type: EntityType; fixedFilters: Record<string, string> } {
  return tab === 'Bugs' ? { type: 'Todo', fixedFilters: { kind: 'bug' } } : { type: tab, fixedFilters: {} };
}

// PM-table-style browse: pick a tab, filter on any column that type has, click a row
// to drill into EntityView. One page for every type rather than a page per type --
// columns, filters, and the table itself are all driven by introspected schema
// (useColumns), so a new type or a new column on an existing type needs no change
// here, only DEFAULT_COLUMNS/EDITABLE_COLUMNS on the backend if it should be shown.
export default function BrowseView() {
  const { type } = useParams<{ type: string }>();
  const tab = (TABS as readonly string[]).includes(type ?? '') ? (type as Tab) : 'Todo';
  const { type: entityType, fixedFilters } = resolveTab(tab);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const columns = useColumns(entityType);
  const columnList = Object.values(columns);
  const shownColumns = columnList.filter((c) => c.shown);
  // "title" is always shown via the table's fixed leading link column -- an extra
  // "Title" column would just repeat it.
  const shownTableColumns = shownColumns.filter((c) => c.name !== 'title');
  const { entities, loading, error, applyFieldSave } = useEntityList(entityType, { ...filters, ...fixedFilters });

  const handleFilterChange = (column: string, value: string) => {
    setFilters((prev) => ({ ...prev, [column]: value }));
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <h1 style={{ margin: 0, fontSize: 20 }}>Browse</h1>
      <EntityTypeTabs types={[...TABS]} active={tab} />
      <AvailableColumns columns={columnList} />
      <GenericFilters columns={shownColumns} values={filters} onChange={handleFilterChange} />
      {loading && <p style={{ color: tokens.color.textMuted }}>Loading...</p>}
      {error && <p style={{ color: tokens.color.danger }}>{error}</p>}
      {!loading && !error && <EntityTable entities={entities} columns={shownTableColumns} onFieldSaved={applyFieldSave} />}
    </div>
  );
}
