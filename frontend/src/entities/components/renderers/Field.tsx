import { useState } from 'react';
import { tokens } from '../../../shared/tokens';
import { useFieldEdit } from '../../hooks/useFieldEdit';
import { rowToEntityDetail } from '../../rowToEntityDetail';
import type { ColumnSchema, EntityDetail, EntityRow, EntityType } from '../../types';
import EditableFieldControl from './EditableFieldControl';
import EnumFieldSelect from './EnumFieldSelect';
import NullableFieldWrapper from './NullableFieldWrapper';
import NumberFieldControl from './NumberFieldControl';

// Identity a renderer passes to make one of its fields editable -- just enough for
// Field to know *what* to call (type/id/field) and *how* to render the control
// (schema, from useColumns). The renderer never talks to the API itself.
export interface EditableFieldProps {
  type: EntityType;
  id: number;
  schema: ColumnSchema;
  onSaved: (entity: EntityDetail) => void;
}

interface FieldProps {
  label: string;
  value: unknown;
  editable?: EditableFieldProps;
}

// Shared field-row layout used by every type-specific renderer, so each renderer
// only has to say which fields it cares about, not how a label/value pair looks --
// or, when `editable` is passed, not how editing works either. An enum field is
// always a live dropdown (EnumFieldSelect, saves on change); text/number fields need
// an explicit click-to-edit session (EditableFieldControl/NumberFieldControl,
// Save/Cancel) since a keystroke isn't a complete value the way picking an option is.
// A nullable field additionally gets NullableFieldWrapper's clear/set-value
// affordance around whichever of those controls applies -- nullability composes with
// any kind rather than each control handling it itself.
export default function Field({ label, value, editable }: FieldProps) {
  const [isEditing, setIsEditing] = useState(false);
  const isEmpty = value === null || value === undefined || value === '';
  const nullable = editable?.schema.nullable ?? false;
  const { clear, saving: clearing } = useFieldEdit(
    editable?.type ?? 'Todo',
    editable?.id ?? 0,
    editable?.schema.name ?? '',
  );

  if (isEmpty && !nullable) return null;

  if (editable && nullable) {
    return (
      <div style={{ display: 'flex', gap: 8, fontSize: 13, alignItems: 'center' }}>
        <span style={{ color: tokens.color.textMuted, minWidth: 90 }}>{label}</span>
        <NullableFieldWrapper
          isNull={isEmpty && !isEditing}
          clearing={clearing}
          onClear={() => clear().then((row) => editable.onSaved(rowToEntityDetail(row)))}
          onSetValue={() => setIsEditing(true)}
        >
          <EditableControl editable={editable} value={value} isEditing={isEditing} setIsEditing={setIsEditing} />
        </NullableFieldWrapper>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', gap: 8, fontSize: 13, alignItems: 'center' }}>
      <span style={{ color: tokens.color.textMuted, minWidth: 90 }}>{label}</span>
      <EditableControl editable={editable} value={value} isEditing={isEditing} setIsEditing={setIsEditing} />
    </div>
  );
}

interface EditableControlProps {
  editable?: EditableFieldProps;
  value: unknown;
  isEditing: boolean;
  setIsEditing: (editing: boolean) => void;
}

// Picks the concrete control for this field's kind -- the one place that decision is
// made, shared by both the plain and nullable-wrapped layouts above.
function EditableControl({ editable, value, isEditing, setIsEditing }: EditableControlProps) {
  if (editable?.schema.kind === 'enum') {
    return (
      <EnumFieldSelect
        type={editable.type}
        id={editable.id}
        schema={editable.schema}
        value={String(value ?? '')}
        onSaved={(row) => editable.onSaved(rowToEntityDetail(row))}
      />
    );
  }

  if (editable && isEditing) {
    const onSaved = (row: EntityRow) => {
      setIsEditing(false);
      editable.onSaved(rowToEntityDetail(row));
    };
    if (editable.schema.kind === 'number') {
      return (
        <NumberFieldControl
          type={editable.type}
          id={editable.id}
          schema={editable.schema}
          initialValue={value === null || value === undefined ? '' : String(value)}
          onSaved={onSaved}
          onCancel={() => setIsEditing(false)}
        />
      );
    }
    return (
      <EditableFieldControl
        type={editable.type}
        id={editable.id}
        schema={editable.schema}
        initialValue={value === null || value === undefined ? '' : String(value)}
        onSaved={onSaved}
        onCancel={() => setIsEditing(false)}
      />
    );
  }

  return (
    <span
      style={{ whiteSpace: 'pre-wrap', cursor: editable ? 'pointer' : undefined }}
      onClick={editable ? () => setIsEditing(true) : undefined}
      title={editable ? 'Click to edit' : undefined}
    >
      {value === null || value === undefined || value === '' ? '—' : String(value)}
    </span>
  );
}
