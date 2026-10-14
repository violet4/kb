import { useEffect, useId, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import { tokens } from './tokens';

interface PopoverProps {
  label: ReactNode;
  // A node stays mounted while hidden; a function mounts only while open (so its contents
  // can autofocus and start fresh each time) and receives `close`.
  children: ReactNode | ((close: () => void) => ReactNode);
  // Which trigger edge the popover lines up with: 'end' (default) grows leftward, for
  // triggers near the right of the screen; 'start' grows rightward, for a left sidebar.
  align?: 'start' | 'end';
  ariaLabel?: string;
  title?: string;
  triggerStyle?: CSSProperties; // replaces the default bordered-button look
}

/** A button that reveals floating content anchored below it, dismissed by an outside
 * click or Escape. Built on the native Popover API (HTMLElement.popover) rather than
 * a hand-rolled positioned-div + outside-click-listener implementation -- the platform
 * already handles light-dismiss, Escape, and top-layer stacking (kb instructions #1,
 * idiomatic platform APIs over lower-level reimplementation), same rationale as
 * Modal's use of <dialog>. anchorName/positionAnchor (CSS anchor positioning) place
 * the popover under its trigger button without manual coordinate math. */
export default function Popover({ label, children, align = 'end', ariaLabel, title, triggerStyle }: PopoverProps) {
  const id = useId();
  const popoverId = `popover-${id}`;
  const anchorName = `--popover-anchor-${id}`;
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (triggerRef.current) triggerRef.current.style.setProperty('anchor-name', anchorName);
  }, [anchorName]);

  const close = () => popoverRef.current?.hidePopover();

  return (
    <>
      <button
        ref={triggerRef}
        popoverTarget={popoverId}
        type="button"
        aria-label={ariaLabel}
        title={title}
        style={
          triggerStyle ?? {
            background: tokens.color.surface,
            color: tokens.color.text,
            border: `1px solid ${tokens.color.border}`,
            borderRadius: 4,
            padding: '4px 10px',
            fontSize: 13,
            cursor: 'pointer',
          }
        }
      >
        {label}
      </button>
      <div
        ref={popoverRef}
        id={popoverId}
        popover="auto"
        onToggle={(e) => setOpen((e.nativeEvent as ToggleEvent).newState === 'open')}
        style={
          {
            positionAnchor: anchorName,
            top: 'calc(anchor(bottom) + 6px)',
            // The UA popover style is inset: 0; the unused side must be auto, or left: 0 wins.
            ...(align === 'end' ? { left: 'auto', right: 'anchor(right)' } : { left: 'anchor(left)', right: 'auto' }),
            margin: 0,
            padding: 12,
            background: tokens.color.surface,
            color: tokens.color.text,
            border: `1px solid ${tokens.color.border}`,
            borderRadius: 6,
            minWidth: 220,
          } as CSSProperties
        }
      >
        {typeof children === 'function' ? open && children(close) : children}
      </div>
    </>
  );
}
