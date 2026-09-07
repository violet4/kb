import Field from './Field';
import { editableFieldProps } from './editableProps';
import type { RendererProps } from './RendererProps';

export default function InstructionView(props: RendererProps) {
  const f = props.entity.fields;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <Field label="Trigger" value={f.trigger} editable={editableFieldProps(props, 'trigger')} />
      <Field label="System level" value={f.system_level} editable={editableFieldProps(props, 'system_level')} />
      <Field label="Body" value={f.body} editable={editableFieldProps(props, 'body')} markdown />
    </div>
  );
}
