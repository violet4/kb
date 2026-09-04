import { useEffect, useId, useRef } from 'react';
import { tokens } from './tokens';

interface PopoverProps {
  label: React.ReactNode;
  children: React.ReactNode;
}

/** A button that reveals floating content anchored below it, dismissed by an outside
 * click or Escape. Built on the native Popover API (HTMLElement.popover) rather than
 * a hand-rolled positioned-div + outside-click-listener implementation -- the platform
 * already handles light-dismiss, Escape, and top-layer stacking (kb instructions #1,
 * idiomatic platform APIs over lower-level reimplementation), same rationale as
 * Modal's use of <dialog>. anchorName/positionAnchor (CSS anchor positioning) place
 * the popover under its trigger button without manual coordinate math. */
export default function Popover({ label, children }: PopoverProps) {
  const id = useId();
  const popoverId = `popover-${id}`;
  const anchorName = `--popover-anchor-${id}`;
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (triggerRef.current) triggerRef.current.style.setProperty('anchor-name', anchorName);
  }, [anchorName]);

  return (
    <>
      <button
        ref={triggerRef}
        popoverTarget={popoverId}
        type="button"
        style={{
          background: tokens.color.surface,
          color: tokens.color.text,
          border: `1px solid ${tokens.color.border}`,
          borderRadius: 4,
          padding: '4px 10px',
          fontSize: 13,
          cursor: 'pointer',
        }}
      >
        {label}
      </button>
      <div
        id={popoverId}
        popover="auto"
        style={
          {
            positionAnchor: anchorName,
            top: 'calc(anchor(bottom) + 6px)',
            right: `calc(100% - anchor(right))`,
            margin: 0,
            padding: 12,
            background: tokens.color.surface,
            color: tokens.color.text,
            border: `1px solid ${tokens.color.border}`,
            borderRadius: 6,
            minWidth: 220,
          } as React.CSSProperties
        }
      >
        {children}
      </div>
    </>
  );
}
