import { useState } from 'react';
import { Link } from 'react-router-dom';
import Popover from '../../shared/Popover';
import { tokens } from '../../shared/tokens';
import { setPlacement } from '../api';
import type { Placement } from '../types';
import { useContextLink } from '../useContextLink';
import ContextPicker from './ContextPicker';

// A record's placement, shown as a link to its context page (or its #tag), with a pencil
// beside it that opens the context picker. Used by the Browse table and the record page.
export default function PlacementControl({
  type,
  id,
  placement,
  nullable,
  onSaved,
}: {
  type: string;
  id: number;
  placement: Placement;
  nullable: boolean;
  onSaved: (placement: Placement) => void;
}) {
  const contextLink = useContextLink();
  const [error, setError] = useState<string | null>(null);

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, whiteSpace: 'nowrap' }}>
      {placement.context ? (
        <Link to={contextLink(placement.context.id)} style={tokens.link}>
          @{placement.context.name}
        </Link>
      ) : placement.tag ? (
        <span title="Floats to every context carrying this tag">#{placement.tag.name}</span>
      ) : (
        <span style={{ color: tokens.color.textMuted }}>none</span>
      )}
      <Popover
        label="✎"
        align="start"
        title="Change context"
        ariaLabel="Change context"
        triggerStyle={{
          background: 'none',
          border: 'none',
          padding: 0,
          color: tokens.color.textMuted,
          cursor: 'pointer',
          fontSize: 12,
        }}
      >
        {(close) => (
          <ContextPicker
            value={placement}
            nullable={nullable}
            onCancel={close}
            onPick={(choice) => {
              close();
              setPlacement(type, id, choice)
                .then((saved) => {
                  setError(null);
                  onSaved(saved);
                })
                .catch((e) => setError(e instanceof Error ? e.message : String(e)));
            }}
          />
        )}
      </Popover>
      {error && <span style={{ color: tokens.color.danger, fontSize: 12 }}>{error}</span>}
    </span>
  );
}
