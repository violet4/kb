import { useState } from 'react';
import { isoDateTime } from '../../shared/isoDate';
import { tokens } from '../../shared/tokens';
import { setEntityDeleted } from '../api';
import { rowToEntityDetail } from '../rowToEntityDetail';
import type { EntityDetail } from '../types';

const linkButton = { ...tokens.link, background: 'none', border: 'none', padding: 0, cursor: 'pointer', fontSize: 12 } as const;

// Soft delete beside the record's title: one click asks, a second confirms. A deleted record
// stays on this page, marked, with restore beside the mark.
export default function DeleteControl({
  entity,
  onChanged,
}: {
  entity: EntityDetail;
  onChanged: (entity: EntityDetail) => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const apply = async (deleted: boolean) => {
    setBusy(true);
    setError(null);
    try {
      onChanged(rowToEntityDetail(await setEntityDeleted(entity.type, entity.id, deleted)));
      setConfirming(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <span style={{ display: 'inline-flex', alignItems: 'baseline', gap: 8, fontSize: 12 }}>
      {entity.deleted_at ? (
        <>
          <span style={{ color: tokens.color.danger }}>deleted {isoDateTime(entity.deleted_at)}</span>
          <button style={linkButton} disabled={busy} onClick={() => apply(false)}>
            restore
          </button>
        </>
      ) : confirming ? (
        <>
          <span style={{ color: tokens.color.danger }}>delete this {entity.type.toLowerCase()}?</span>
          <button style={{ ...linkButton, color: tokens.color.danger }} disabled={busy} onClick={() => apply(true)}>
            yes, delete
          </button>
          <button style={linkButton} disabled={busy} onClick={() => setConfirming(false)}>
            cancel
          </button>
        </>
      ) : (
        <button style={{ ...linkButton, color: tokens.color.textMuted }} onClick={() => setConfirming(true)}>
          delete
        </button>
      )}
      {error && <span style={{ color: tokens.color.danger }}>{error}</span>}
    </span>
  );
}
