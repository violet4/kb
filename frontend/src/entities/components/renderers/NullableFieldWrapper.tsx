import type { ReactNode } from 'react';
import { tokens } from '../../../shared/tokens';

interface NullableFieldWrapperProps {
  isNull: boolean;
  clearing: boolean;
  onClear: () => void;
  onSetValue: () => void;
  children: ReactNode;
}

// Generic nullable-or-value affordance: composes around whichever concrete control
// (enum select, text edit session, number edit session) Field decides to render, with
// no awareness of what that control actually is. Null state shows a plain
// "— (click to set)" placeholder that hands off to the normal edit flow; non-null
// state renders the concrete control plus a small clear (x) button next to it.
export default function NullableFieldWrapper({ isNull, clearing, onClear, onSetValue, children }: NullableFieldWrapperProps) {
  if (isNull) {
    return (
      <span
        onClick={onSetValue}
        title="Click to set"
        style={{ color: tokens.color.textMuted, cursor: 'pointer', fontSize: 13 }}
      >
        — (click to set)
      </span>
    );
  }
  return (
    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
      {children}
      <button
        onClick={onClear}
        disabled={clearing}
        title="Clear"
        style={{
          background: 'transparent',
          border: 'none',
          color: tokens.color.textMuted,
          cursor: 'pointer',
          fontSize: 13,
          padding: '0 4px',
          lineHeight: 1,
        }}
      >
        ×
      </button>
    </div>
  );
}
