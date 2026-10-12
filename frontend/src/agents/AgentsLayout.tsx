import { Link, Outlet, useLocation } from 'react-router-dom';
import { tokens } from '../shared/tokens';

type AgentsTab = 'current' | 'project' | 'recency';

function activeTab(pathname: string): AgentsTab {
  if (pathname === '/agents/history/recent') return 'recency';
  if (pathname.startsWith('/agents/history')) return 'project';
  return 'current';
}

// The Agents page: one heading and one tab strip over its three session lists -- live
// sessions (AgentsView) and past sessions by project or by recency (AgentHistoryView). Each
// tab is its own route, so a tab is linkable and the browser's back button moves between them.
export default function AgentsLayout() {
  const tab = activeTab(useLocation().pathname);
  const tabStyle = (isActive: boolean): React.CSSProperties => ({
    padding: '4px 10px',
    borderRadius: 6,
    fontSize: 13,
    textDecoration: 'none',
    color: isActive ? tokens.color.text : tokens.color.textMuted,
    background: isActive ? tokens.color.border : 'transparent',
  });
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <h1 style={{ margin: 0, fontSize: 20 }}>Agents</h1>
        <nav style={{ display: 'flex', gap: 4 }}>
          <Link to="/agents" style={tabStyle(tab === 'current')} aria-current={tab === 'current' ? 'page' : undefined}>
            Current
          </Link>
          <Link to="/agents/history" style={tabStyle(tab === 'project')} aria-current={tab === 'project' ? 'page' : undefined}>
            By Project
          </Link>
          <Link
            to="/agents/history/recent"
            style={tabStyle(tab === 'recency')}
            aria-current={tab === 'recency' ? 'page' : undefined}
          >
            By Recency
          </Link>
        </nav>
      </div>
      <Outlet />
    </div>
  );
}
