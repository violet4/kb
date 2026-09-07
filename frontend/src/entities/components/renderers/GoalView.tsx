import Field from './Field';
import { editableFieldProps } from './editableProps';
import type { RendererProps } from './RendererProps';

export default function GoalView(props: RendererProps) {
  const f = props.entity.fields;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <Field label="Status" value={f.status} editable={editableFieldProps(props, 'status')} />
      <Field label="Description" value={f.description} editable={editableFieldProps(props, 'description')} markdown />
      <Field label="Notes" value={f.notes} editable={editableFieldProps(props, 'notes')} markdown />
    </div>
  );
}
