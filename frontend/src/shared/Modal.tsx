import { useEffect, useRef } from 'react';
import { tokens } from './tokens';

interface ModalProps {
  open: boolean;
  onClose: () => void;
  /** Called instead of closing when Escape is pressed or the backdrop is clicked, if
   * provided -- return true to allow the close, false to block it. Lets a caller with
   * unsaved changes (e.g. EventFormModal) require an explicit Cancel/Save instead of a
   * quick-dismiss losing the edit. Omit for a plain always-closable modal. */
  onRequestClose?: () => boolean;
  children: React.ReactNode;
}

/** Thin wrapper over the native <dialog> element -- it handles focus-trapping, Escape-
 * to-close, and backdrop rendering natively, so there's no reason to hand-roll those
 * (kb instructions #1, use idiomatic platform APIs over lower-level reimplementation).
 * showModal()/close() are imperative dialog APIs with no declarative React prop for
 * "open," so a ref + effect is the correct seam here (kb instructions #41 permits
 * useRef+useEffect with real logic once named/extracted, which this is). */
export default function Modal({ open, onClose, onRequestClose, children }: ModalProps) {
  const ref = useRef<HTMLDialogElement>(null);
  useDialogOpenState(ref, open, onClose);

  return (
    <dialog
      ref={ref}
      onCancel={(e) => {
        if (onRequestClose && !onRequestClose()) e.preventDefault();
      }}
      onKeyDownCapture={(e) => {
        // Some native controls (<input type="date">'s spin buttons in particular)
        // handle Escape themselves -- reverting their own in-progress edit -- and
        // never let the keydown reach <dialog>'s built-in Escape-to-cancel behavior,
        // so onCancel above never fires and onRequestClose's dirty-check is bypassed
        // entirely while focus sits in one of those controls. Capture-phase Escape
        // here runs before any such field-level handler, so it's the one place this
        // can be caught application-wide regardless of which control has focus.
        if (e.key === 'Escape' && onRequestClose && !onRequestClose()) {
          e.preventDefault();
          e.stopPropagation();
        }
      }}
      onClick={(e) => {
        if (e.target === ref.current && (!onRequestClose || onRequestClose())) onClose();
      }}
      style={{
        background: tokens.color.surface,
        color: tokens.color.text,
        border: `1px solid ${tokens.color.border}`,
        borderRadius: 8,
        padding: 0,
      }}
    >
      {children}
    </dialog>
  );
}

function useDialogOpenState(ref: React.RefObject<HTMLDialogElement | null>, open: boolean, onClose: () => void): void {
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();

    // Keep React state in sync if the dialog closes itself (Escape key), so onClose
    // still fires and the caller's `open` state doesn't go stale.
    const handleClose = () => onClose();
    dialog.addEventListener('close', handleClose);
    return () => dialog.removeEventListener('close', handleClose);
  }, [open, onClose]);
}
