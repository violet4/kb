import { tokens } from '../../shared/tokens';
import type { EntityDetail } from '../types';

interface EntityHeaderProps {
  entity: EntityDetail;
}

export default function EntityHeader({ entity }: EntityHeaderProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <p style={{ margin: 0, fontSize: 13, color: tokens.color.textMuted }}>
        {entity.type}:{entity.id}
        {entity.context_name ? ` · ${entity.context_name}` : ''}
      </p>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <h1 style={{ margin: 0, fontSize: 20 }}>{entity.label}</h1>
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
