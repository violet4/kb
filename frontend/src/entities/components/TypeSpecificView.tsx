import { tokens } from '../../shared/tokens';
import type { ColumnSchema, EntityDetail } from '../types';
import ArchivedLinkView from './renderers/ArchivedLinkView';
import DailyView from './renderers/DailyView';
import GoalView from './renderers/GoalView';
import IdeaView from './renderers/IdeaView';
import InstructionView from './renderers/InstructionView';
import NoteView from './renderers/NoteView';
import TodoView from './renderers/TodoView';
import WishlistView from './renderers/WishlistView';

interface TypeSpecificViewProps {
  entity: EntityDetail;
  schemas: Record<string, ColumnSchema>;
  onFieldSaved: (entity: EntityDetail) => void;
}

// One renderer per entity type -- open for extension (add a new type + case here)
// without modifying the existing renderers. Column schemas are fetched once by
// EntityView (shared with EntityHeader's title editing) and passed down here, so
// every renderer shares the same schema lookup rather than each fetching its own.
export default function TypeSpecificView({ entity, schemas, onFieldSaved }: TypeSpecificViewProps) {
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
    case 'Instruction':
      return <InstructionView entity={entity} schemas={schemas} onFieldSaved={onFieldSaved} />;
    case 'Daily':
      return <DailyView entity={entity} schemas={schemas} onFieldSaved={onFieldSaved} />;
    case 'ArchivedLink':
      return <ArchivedLinkView entity={entity} schemas={schemas} onFieldSaved={onFieldSaved} />;
    default:
      return <p style={{ color: tokens.color.textMuted }}>No renderer for {entity.type}.</p>;
  }
}
