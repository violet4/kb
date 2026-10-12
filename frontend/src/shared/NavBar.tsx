import { Fragment } from 'react';
import { Link } from 'react-router-dom';
import { tokens } from './tokens';

// Related views sit together; a vertical rule separates the groups.
const GROUPS: { to: string; label: string }[][] = [
  [
    { to: '/contexts', label: 'Contexts' },
    { to: '/search', label: 'Search' },
    { to: '/browse', label: 'Browse' },
  ],
  [
    { to: '/', label: 'Dailies' },
    { to: '/events', label: 'Events' },
    { to: '/log', label: 'Log' },
  ],
  [
    { to: '/usage', label: 'Usage' },
    { to: '/agents', label: 'Agents' },
    { to: '/channels', label: 'Channels' },
  ],
];

export default function NavBar() {
  return (
    <nav
      style={{
        display: 'flex',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: 14,
        padding: '12px 24px',
        borderBottom: `1px solid ${tokens.color.border}`,
      }}
    >
      {GROUPS.map((group, i) => (
        <Fragment key={group[0].to}>
          {i > 0 && <span aria-hidden style={{ alignSelf: 'stretch', width: 1, background: tokens.color.border }} />}
          {group.map((item) => (
            <Link key={item.to} to={item.to} style={{ color: tokens.color.text, textDecoration: 'none', fontSize: 13 }}>
              {item.label}
            </Link>
          ))}
        </Fragment>
      ))}
    </nav>
  );
}
