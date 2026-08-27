import type { EditableFieldProps } from './Field';
import type { RendererProps } from './RendererProps';

// Shared by every renderer: builds the `editable` prop for one Field, or undefined
// if that field isn't in this type's editable-field allowlist (schemas won't have
// an entry for it) -- so a renderer just calls editableFieldProps(renderer, field)
// per field rather than repeating the {type, id, schema, onSaved} shape five times over.
export function editableFieldProps(
  { entity, schemas, onFieldSaved }: Pick<RendererProps, 'entity' | 'schemas' | 'onFieldSaved'>,
  field: string,
): EditableFieldProps | undefined {
  const schema = schemas[field];
  if (!schema) return undefined;
  return { type: entity.type, id: entity.id, schema, onSaved: onFieldSaved };
}
