import { Link } from 'react-router-dom';
import { tokens } from '../../shared/tokens';

interface EntityTypeTabsProps {
  types: string[];
  active: string;
}

// Tab keys are usually an EntityType, but a tab can also be a named filtered view
// (e.g. "Bugs" = Todo with kind=bug) that BrowseView resolves to a real type + filter --
// kept as plain strings here since the tab bar itself doesn't need to know the difference.
export default function EntityTypeTabs({ types, active }: EntityTypeTabsProps) {
  return (
    <div style={{ display: 'flex', gap: 12 }}>
      {types.map((t) => (
        <Link
          key={t}
          to={`/browse/${t}`}
          style={{
            fontSize: 13,
            textDecoration: 'none',
            color: t === active ? tokens.color.accent : tokens.color.textMuted,
            fontWeight: t === active ? 600 : 400,
          }}
        >
          {t}
        </Link>
      ))}
    </div>
  );
}
