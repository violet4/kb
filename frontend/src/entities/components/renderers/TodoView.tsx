import Field from './Field';
import { editableFieldProps } from './editableProps';
import type { RendererProps } from './RendererProps';

export default function TodoView(props: RendererProps) {
  const f = props.entity.fields;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <Field label="Status" value={f.status} editable={editableFieldProps(props, 'status')} />
      <Field label="Kind" value={f.kind} editable={editableFieldProps(props, 'kind')} />
      <Field label="Effort" value={f.effort} />
      <Field label="Severity" value={f.severity} editable={editableFieldProps(props, 'severity')} />
      <Field label="Urgent" value={f.urgent ? 'yes' : null} />
      <Field label="Notes" value={f.notes} editable={editableFieldProps(props, 'notes')} />
    </div>
  );
}
