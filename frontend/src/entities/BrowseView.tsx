import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { tokens } from '../shared/tokens';
import EntityTable from './components/EntityTable';
import EntityTypeTabs from './components/EntityTypeTabs';
import GenericFilters from './components/GenericFilters';
import { useColumns } from './hooks/useColumns';
import { useEntityList } from './hooks/useEntityList';
import { labelColumnName } from './labelColumn';
import type { EntityType } from './types';

const TABS = ['Todo', 'Bugs', 'Goal', 'Note', 'Idea', 'Wishlist', 'Instruction', 'Daily', 'ArchivedLink'] as const;
type Tab = (typeof TABS)[number];

// "Bugs" isn't a real entity type -- it's Todo with kind=bug (same table/lifecycle
// as Todo, see CLAUDE.md) -- so its tab resolves to Todo's own type + a fixed extra
// filter rather than being a separate entry in ENTITY_TYPES.
function resolveTab(tab: Tab): { type: EntityType; fixedFilters: Record<string, string> } {
  return tab === 'Bugs' ? { type: 'Todo', fixedFilters: { kind: 'bug' } } : { type: tab, fixedFilters: {} };
}

// What a tab's user-editable filters start at on first load -- an editorial choice
// (which statuses are "still relevant to look at by default"), not derivable from
// the schema. The user can always clear/change these; they're just the starting
// point. Status values are comma-joined since the status filter is a multi-select
// (see GenericFilters/EnumMultiSelectFilter) -- one filter value can mean several
// enum members via the same IN-based backend match multi-select already uses.
const DEFAULT_FILTERS: Partial<Record<Tab, Record<string, string>>> = {
  Todo: { status: 'pending,in_progress' },
  Bugs: { status: 'pending,in_progress' },
  Goal: { status: 'active,on_hold' },
  Idea: { status: 'active,promoted' },
  Wishlist: { status: 'active' },
  Daily: { is_active: 'true' },
};

// PM-table-style browse: pick a tab, filter on any column that type has, click a row
// to drill into EntityView. One page for every type rather than a page per type --
// columns, filters, and the table itself are all driven by introspected schema
// (useColumns), so a new type or a new column on an existing type needs no change
// here, only DEFAULT_COLUMNS/EDITABLE_COLUMNS on the backend if it should be shown.
export default function BrowseView() {
  const { type } = useParams<{ type: string }>();
  const tab = (TABS as readonly string[]).includes(type ?? '') ? (type as Tab) : 'Todo';
  const { type: entityType, fixedFilters } = resolveTab(tab);
  const [filters, setFilters] = useState<Record<string, string>>(() => DEFAULT_FILTERS[tab] ?? {});
  // Re-seed from this tab's own defaults on navigating between tabs -- filters is
  // otherwise per-mount state, shared across a whole BrowseView lifetime spanning
  // several tabs (the route param changes without unmounting the component).
  useEffect(() => {
    setFilters(DEFAULT_FILTERS[tab] ?? {});
  }, [tab]);
  const columns = useColumns(entityType);
  const columnList = Object.values(columns);
  const shownColumns = columnList.filter((c) => c.shown);
  // Whichever column backs this row's label is already shown via the table's fixed
  // leading link column -- an extra column for it would just repeat the same text.
  const labelColumns = new Set([labelColumnName(entityType)]);
  const shownTableColumns = shownColumns.filter((c) => !labelColumns.has(c.name));
  const { entities, loading, error, applyFieldSave } = useEntityList(entityType, { ...filters, ...fixedFilters });

  const handleFilterChange = (column: string, value: string) => {
    setFilters((prev) => ({ ...prev, [column]: value }));
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <h1 style={{ margin: 0, fontSize: 20 }}>Browse</h1>
      <EntityTypeTabs types={[...TABS]} active={tab} />
      <GenericFilters columns={shownColumns} values={filters} onChange={handleFilterChange} />
      {loading && <p style={{ color: tokens.color.textMuted }}>Loading...</p>}
      {error && <p style={{ color: tokens.color.danger }}>{error}</p>}
      {!loading && !error && (
        <EntityTable
          entities={entities}
          columns={shownTableColumns}
          titleSchema={columns[labelColumnName(entityType)]}
          onFieldSaved={applyFieldSave}
        />
      )}
    </div>
  );
}
