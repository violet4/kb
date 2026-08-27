import type { ColumnSchema, EntityDetail } from '../../types';

// Shared prop shape for every type-specific renderer -- entity to render, the
// column schemas fetched once by TypeSpecificView, and the callback to run after
// any field save (so EntityView can refresh its Journal panel).
export interface RendererProps {
  entity: EntityDetail;
  schemas: Record<string, ColumnSchema>;
  onFieldSaved: (entity: EntityDetail) => void;
}
