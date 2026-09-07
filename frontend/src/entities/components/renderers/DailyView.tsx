import Field from './Field';
import { editableFieldProps } from './editableProps';
import type { RendererProps } from './RendererProps';

export default function DailyView(props: RendererProps) {
  const f = props.entity.fields;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <Field label="Domain" value={f.domain} editable={editableFieldProps(props, 'domain')} />
      <Field label="Tier" value={f.tier} editable={editableFieldProps(props, 'tier')} />
      <Field label="Recurrence" value={f.recurrence} editable={editableFieldProps(props, 'recurrence')} />
      <Field label="Is active" value={f.is_active} editable={editableFieldProps(props, 'is_active')} />
      <Field label="Location" value={f.location} editable={editableFieldProps(props, 'location')} />
      <Field label="Next due date" value={f.next_due_date} />
      <Field label="Notes" value={f.notes} editable={editableFieldProps(props, 'notes')} markdown />
    </div>
  );
}
