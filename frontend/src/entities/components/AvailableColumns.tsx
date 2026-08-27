import { tokens } from '../../shared/tokens';
import type { ColumnSchema } from '../types';

interface AvailableColumnsProps {
  columns: ColumnSchema[];
}

// Plain-text enumeration of every real column this type has that the table doesn't
// currently show -- lets a missing-but-wanted column get spotted and promoted to
// DEFAULT_COLUMNS deliberately, rather than needing to already know the schema.
export default function AvailableColumns({ columns }: AvailableColumnsProps) {
  const hidden = columns.filter((c) => !c.shown);
  if (hidden.length === 0) return null;
  return (
    <p style={{ margin: 0, fontSize: 12, color: tokens.color.textMuted }}>
      Also available: {hidden.map((c) => `${c.name} (${c.kind})`).join(', ')}
    </p>
  );
}
