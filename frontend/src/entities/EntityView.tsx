import { useParams } from 'react-router-dom';
import { tokens } from '../shared/tokens';
import EntityHeader from './components/EntityHeader';
import GraphPanel from './components/GraphPanel';
import JournalPanel from './components/JournalPanel';
import TypeSpecificView from './components/TypeSpecificView';
import { useColumns } from './hooks/useColumns';
import { useEntity } from './hooks/useEntity';
import { labelColumnName } from './labelColumn';
import type { EntityType } from './types';

// The generic interface every entity gets: header, its own type-specific renderer
// embedded in the middle, then the two cross-entity sections (graph links, journal
// history) that apply uniformly regardless of type. Column schemas are fetched once
// here (one request per entity view) and shared by both the header's title editing
// and TypeSpecificView's per-field editing.
export default function EntityView() {
  const { type, id } = useParams<{ type: string; id: string }>();
  const entityType = type as EntityType;
  const entityId = Number(id);
  const { entity, graph, journal, loading, error, applyFieldSave } = useEntity(entityType, entityId);
  const schemas = useColumns(entityType);

  if (loading) return <p style={{ color: tokens.color.textMuted }}>Loading...</p>;
  if (error) return <p style={{ color: tokens.color.danger }}>{error}</p>;
  if (!entity) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <EntityHeader entity={entity} titleSchema={schemas[labelColumnName(entityType)]} onFieldSaved={applyFieldSave} />
      <TypeSpecificView entity={entity} schemas={schemas} onFieldSaved={applyFieldSave} />
      <GraphPanel neighbors={graph} />
      <JournalPanel entries={journal} />
    </div>
  );
}
