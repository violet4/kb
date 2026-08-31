import { Link } from 'react-router-dom';
import { tokens } from './tokens';

export default function NavBar() {
  return (
    <nav style={{ display: 'flex', gap: 16, padding: '12px 24px', borderBottom: `1px solid ${tokens.color.border}` }}>
      <Link to="/" style={{ color: tokens.color.text, textDecoration: 'none', fontSize: 13 }}>
        Dailies
      </Link>
      <Link to="/events" style={{ color: tokens.color.text, textDecoration: 'none', fontSize: 13 }}>
        Events
      </Link>
      <Link to="/usage" style={{ color: tokens.color.text, textDecoration: 'none', fontSize: 13 }}>
        Usage
      </Link>
      <Link to="/agents" style={{ color: tokens.color.text, textDecoration: 'none', fontSize: 13 }}>
        Agents
      </Link>
      <Link to="/channels" style={{ color: tokens.color.text, textDecoration: 'none', fontSize: 13 }}>
        Channels
      </Link>
      <Link to="/browse" style={{ color: tokens.color.text, textDecoration: 'none', fontSize: 13 }}>
        Browse
      </Link>
      <Link to="/search" style={{ color: tokens.color.text, textDecoration: 'none', fontSize: 13 }}>
        Search
      </Link>
    </nav>
  );
}
