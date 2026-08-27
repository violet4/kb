import { useParams } from 'react-router-dom';
import { tokens } from '../shared/tokens';
import EntityHeader from './components/EntityHeader';
import GraphPanel from './components/GraphPanel';
import JournalPanel from './components/JournalPanel';
import TypeSpecificView from './components/TypeSpecificView';
import { useEntity } from './hooks/useEntity';
import type { EntityType } from './types';

// The generic interface every entity gets: header, its own type-specific renderer
// embedded in the middle, then the two cross-entity sections (graph links, journal
// history) that apply uniformly regardless of type.
export default function EntityView() {
  const { type, id } = useParams<{ type: string; id: string }>();
  const entityType = type as EntityType;
  const entityId = Number(id);
  const { entity, graph, journal, loading, error, applyFieldSave } = useEntity(entityType, entityId);

  if (loading) return <p style={{ color: tokens.color.textMuted }}>Loading...</p>;
  if (error) return <p style={{ color: tokens.color.danger }}>{error}</p>;
  if (!entity) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <EntityHeader entity={entity} />
      <TypeSpecificView entity={entity} onFieldSaved={applyFieldSave} />
      <GraphPanel neighbors={graph} />
      <JournalPanel entries={journal} />
    </div>
  );
}
