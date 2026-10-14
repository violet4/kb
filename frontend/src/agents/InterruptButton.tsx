import { useState } from 'react';
import { tokens } from '../shared/tokens';

interface InterruptButtonProps {
  onInterrupt: () => Promise<void>;
  // Why Esc can't be pressed now (from the server), or null when it can.
  blocker: string | null;
}

// Presses Esc in the session's terminal, interrupting the running turn. A failure shows on the
// button itself (its tooltip carries the reason), so nothing else on the page moves.
export default function InterruptButton({ onInterrupt, blocker }: InterruptButtonProps) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const disabled = busy || blocker !== null;

  async function interrupt() {
    if (disabled) return;
    setBusy(true);
    setError(null);
    try {
      await onInterrupt();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      onClick={interrupt}
      disabled={disabled}
      title={error ?? blocker ?? 'Interrupt the running turn (Esc)'}
      style={{
        padding: '8px 12px',
        borderRadius: 6,
        border: `1px solid ${error ? tokens.color.danger : tokens.color.border}`,
        background: 'transparent',
        color: error ? tokens.color.danger : tokens.color.text,
        fontSize: 13,
        cursor: disabled ? 'default' : 'pointer',
        opacity: disabled ? 0.5 : 1,
      }}
    >
      Esc
    </button>
  );
}
