import { useEffect, useRef } from 'react';
import { tokens } from './tokens';

interface ModalProps {
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
}

/** Thin wrapper over the native <dialog> element -- it handles focus-trapping, Escape-
 * to-close, and backdrop rendering natively, so there's no reason to hand-roll those
 * (kb instructions #1, use idiomatic platform APIs over lower-level reimplementation).
 * showModal()/close() are imperative dialog APIs with no declarative React prop for
 * "open," so a ref + effect is the correct seam here (kb instructions #41 permits
 * useRef+useEffect with real logic once named/extracted, which this is). */
export default function Modal({ open, onClose, children }: ModalProps) {
  const ref = useRef<HTMLDialogElement>(null);
  useDialogOpenState(ref, open, onClose);

  return (
    <dialog
      ref={ref}
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
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
