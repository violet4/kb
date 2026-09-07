import Field from './Field';
import { editableFieldProps } from './editableProps';
import type { RendererProps } from './RendererProps';

export default function NoteView(props: RendererProps) {
  const f = props.entity.fields;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <Field label="Collection" value={f.collection} editable={editableFieldProps(props, 'collection')} />
      <Field label="Tags" value={f.tags} editable={editableFieldProps(props, 'tags')} />
      <Field label="Body" value={f.body} editable={editableFieldProps(props, 'body')} markdown />
    </div>
  );
}
