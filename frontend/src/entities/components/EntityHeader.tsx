import { useState } from 'react';
import { tokens } from '../../shared/tokens';
import { rowToEntityDetail } from '../rowToEntityDetail';
import type { ColumnSchema, EntityDetail } from '../types';
import EditableFieldControl from './renderers/EditableFieldControl';

interface EntityHeaderProps {
  entity: EntityDetail;
  titleSchema?: ColumnSchema;
  onFieldSaved: (entity: EntityDetail) => void;
}

export default function EntityHeader({ entity, titleSchema, onFieldSaved }: EntityHeaderProps) {
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <p style={{ margin: 0, fontSize: 13, color: tokens.color.textMuted }}>
        {entity.type}:{entity.id}
        {entity.context_name ? ` · ${entity.context_name}` : ''}
      </p>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        {titleSchema && isEditingTitle ? (
          <EditableFieldControl
            type={entity.type}
            id={entity.id}
            schema={titleSchema}
            initialValue={entity.label}
            onSaved={(row) => {
              setIsEditingTitle(false);
              onFieldSaved(rowToEntityDetail(row));
            }}
            onCancel={() => setIsEditingTitle(false)}
          />
        ) : (
          <h1
            style={{ margin: 0, fontSize: 20, cursor: titleSchema ? 'pointer' : undefined }}
            onClick={titleSchema ? () => setIsEditingTitle(true) : undefined}
            title={titleSchema ? 'Click to edit' : undefined}
          >
            {entity.label}
          </h1>
        )}
        {entity.status && (
          <span
            style={{
              fontSize: 12,
              color: tokens.color.textMuted,
              border: `1px solid ${tokens.color.border}`,
              borderRadius: 4,
              padding: '2px 6px',
            }}
          >
            {entity.status}
          </span>
        )}
      </div>
    </div>
  );
}
