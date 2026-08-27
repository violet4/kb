import { tokens } from '../../../shared/tokens';
import Field from './Field';
import { editableFieldProps } from './editableProps';
import type { RendererProps } from './RendererProps';

export default function ArchivedLinkView(props: RendererProps) {
  const f = props.entity.fields;
  const url = typeof f.url === 'string' ? f.url : null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {url && (
        <div style={{ display: 'flex', gap: 8, fontSize: 13 }}>
          <span style={{ color: tokens.color.textMuted, minWidth: 90 }}>URL</span>
          <a href={url} target="_blank" rel="noreferrer" style={{ color: tokens.color.accent }}>
            {url}
          </a>
        </div>
      )}
      <Field label="Reason" value={f.reason} editable={editableFieldProps(props, 'reason')} />
      <Field label="Push status" value={f.push_status} />
      <Field label="Content status" value={f.content_status} />
    </div>
  );
}
