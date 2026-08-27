import { useState } from 'react';
import { updateEntityField } from '../api';
import type { EntityRow, EntityType } from '../types';

interface UseFieldEditResult {
  save: (value: string) => Promise<EntityRow>;
  clear: () => Promise<EntityRow>;
  saving: boolean;
  error: string | null;
}

// The one place a field PATCH is actually sent -- Field calls this, the renderer
// never talks to the API directly. clear() is the nullable-column counterpart to
// save(): same endpoint, is_null=true instead of a value.
export function useFieldEdit(type: EntityType, id: number, field: string): UseFieldEditResult {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (value: string, isNull: boolean): Promise<EntityRow> => {
    setSaving(true);
    setError(null);
    try {
      return await updateEntityField(type, id, field, value, isNull);
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      setError(message);
      throw e;
    } finally {
      setSaving(false);
    }
  };

  return {
    save: (value) => run(value, false),
    clear: () => run('', true),
    saving,
    error,
  };
}
