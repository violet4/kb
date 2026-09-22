import { useState } from 'react';
import Markdown from '../../../shared/Markdown';
import { tokens } from '../../../shared/tokens';
import { useFieldEdit } from '../../hooks/useFieldEdit';
import { rowToEntityDetail } from '../../rowToEntityDetail';
import type { ColumnSchema, EntityDetail, EntityRow, EntityType } from '../../types';
import BoolFieldToggle from './BoolFieldToggle';
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
  // Render the display (non-editing) value as markdown -- for long free-text
  // fields (Body/Description/Notes) where the source may contain markdown,
  // matching SessionTranscript's chat-message rendering. Editing still shows
  // and edits the raw text; only the read view is rendered as markdown.
  markdown?: boolean;
}

// Shared field-row layout used by every type-specific renderer, so each renderer
// only has to say which fields it cares about, not how a label/value pair looks --
// or, when `editable` is passed, not how editing works either. An enum/bool field is
// always a live control (EnumFieldSelect/BoolFieldToggle, saves on change) that
// renders unconditionally and handles its own empty state (see EnumFieldSelect's
// blank option); text/number fields need an explicit click-to-edit session
// (EditableFieldControl/NumberFieldControl, Save/Cancel) since a keystroke isn't a
// complete value the way picking an option is, so a nullable text/number field gets
// NullableFieldWrapper's placeholder-then-click-to-reveal/clear affordance around it
// -- an always-live control skips that wrapper entirely (see `alwaysLive` below).
export default function Field({ label, value, editable, markdown }: FieldProps) {
  const [isEditing, setIsEditing] = useState(false);
  const isEmpty = value === null || value === undefined || value === '';
  const nullable = editable?.schema.nullable ?? false;
  // enum/bool are always-live controls (EnumFieldSelect/BoolFieldToggle) that
  // render and handle their own empty/null state directly -- gating them behind
  // NullableFieldWrapper's placeholder-then-click-to-reveal flow (built for the
  // click-to-edit-session controls, text/number) would mean a null enum/bool
  // renders no control at all until a first click, with nothing to click into.
  const alwaysLive = editable?.schema.kind === 'enum' || editable?.schema.kind === 'bool';

  const { clear, saving: clearing } = useFieldEdit(
    editable?.type ?? 'Todo',
    editable?.id ?? 0,
    editable?.schema.name ?? '',
  );

  if (isEmpty && !nullable) return null;

  if (editable && nullable && !alwaysLive) {
    return (
      <div style={{ display: 'flex', gap: 8, fontSize: 13, alignItems: 'center' }}>
        <span style={{ color: tokens.color.textMuted, minWidth: 90 }}>{label}</span>
        <NullableFieldWrapper
          isNull={isEmpty && !isEditing}
          clearing={clearing}
          onClear={() => clear().then((row) => editable.onSaved(rowToEntityDetail(row)))}
          onSetValue={() => setIsEditing(true)}
        >
          <EditableControl
            editable={editable}
            value={value}
            isEditing={isEditing}
            setIsEditing={setIsEditing}
            markdown={markdown}
          />
        </NullableFieldWrapper>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', gap: 8, fontSize: 13, alignItems: 'center' }}>
      <span style={{ color: tokens.color.textMuted, minWidth: 90 }}>{label}</span>
      <EditableControl editable={editable} value={value} isEditing={isEditing} setIsEditing={setIsEditing} markdown={markdown} />
    </div>
  );
}

interface EditableControlProps {
  editable?: EditableFieldProps;
  value: unknown;
  isEditing: boolean;
  setIsEditing: (editing: boolean) => void;
  markdown?: boolean;
}

// A double-click landing on an entity-ref link (see Markdown/linkifyEntityRefs) should
// navigate, not enter edit mode -- editing is triggered only when neither click of the
// pair hit a link.
function startEditUnlessRef(e: React.MouseEvent, startEdit: () => void): void {
  if ((e.target as HTMLElement).closest('a.kb-entity-ref')) return;
  startEdit();
}

// Picks the concrete control for this field's kind -- the one place that decision is
// made, shared by both the plain and nullable-wrapped layouts above.
function EditableControl({ editable, value, isEditing, setIsEditing, markdown }: EditableControlProps) {
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

  if (editable?.schema.kind === 'bool') {
    return (
      <BoolFieldToggle
        type={editable.type}
        id={editable.id}
        schema={editable.schema}
        value={Boolean(value)}
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
        markdown={markdown}
      />
    );
  }

  if (markdown && value !== null && value !== undefined && value !== '') {
    return (
      <span
        style={{ cursor: editable ? 'pointer' : undefined }}
        onDoubleClick={editable ? (e) => startEditUnlessRef(e, () => setIsEditing(true)) : undefined}
        title={editable ? 'Double-click to edit' : undefined}
      >
        <Markdown text={String(value)} />
      </span>
    );
  }

  return (
    <span
      style={{ whiteSpace: 'pre-wrap', cursor: editable ? 'pointer' : undefined }}
      onClick={editable ? () => setIsEditing(true) : undefined}
      title={editable ? 'Click to edit' : undefined}
    >
      {value === null || value === undefined ? 'null' : String(value)}
    </span>
  );
}
