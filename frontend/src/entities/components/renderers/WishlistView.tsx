import Field from './Field';
import { editableFieldProps } from './editableProps';
import type { RendererProps } from './RendererProps';

export default function WishlistView(props: RendererProps) {
  const f = props.entity.fields;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <Field label="Status" value={f.status} editable={editableFieldProps(props, 'status')} />
      <Field label="Effort" value={f.effort} />
      <Field label="Priority" value={f.priority} editable={editableFieldProps(props, 'priority')} />
      <Field label="Price min" value={f.price_min} />
      <Field label="Price max" value={f.price_max} />
      <Field label="Notes" value={f.notes} editable={editableFieldProps(props, 'notes')} markdown />
    </div>
  );
}
