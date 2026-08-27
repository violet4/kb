import { tokens } from '../../shared/tokens';
import { useColumns } from '../hooks/useColumns';
import type { EntityDetail } from '../types';
import GoalView from './renderers/GoalView';
import IdeaView from './renderers/IdeaView';
import NoteView from './renderers/NoteView';
import TodoView from './renderers/TodoView';
import WishlistView from './renderers/WishlistView';

interface TypeSpecificViewProps {
  entity: EntityDetail;
  onFieldSaved: (entity: EntityDetail) => void;
}

// One renderer per entity type -- open for extension (add a new type + case here)
// without modifying the existing renderers. Column schemas are fetched once here
// (one request per entity view, not per field) and passed to whichever renderer
// matches, so every renderer shares the same schema lookup.
export default function TypeSpecificView({ entity, onFieldSaved }: TypeSpecificViewProps) {
  const schemas = useColumns(entity.type);
  switch (entity.type) {
    case 'Todo':
      return <TodoView entity={entity} schemas={schemas} onFieldSaved={onFieldSaved} />;
    case 'Goal':
      return <GoalView entity={entity} schemas={schemas} onFieldSaved={onFieldSaved} />;
    case 'Note':
      return <NoteView entity={entity} schemas={schemas} onFieldSaved={onFieldSaved} />;
    case 'Idea':
      return <IdeaView entity={entity} schemas={schemas} onFieldSaved={onFieldSaved} />;
    case 'Wishlist':
      return <WishlistView entity={entity} schemas={schemas} onFieldSaved={onFieldSaved} />;
    default:
      return <p style={{ color: tokens.color.textMuted }}>No renderer for {entity.type}.</p>;
  }
}
