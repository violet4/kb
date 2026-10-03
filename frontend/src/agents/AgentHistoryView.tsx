import { useMemo, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { tokens } from '../shared/tokens';
import { useAgentHistoryProjects, useAgentHistorySessions } from './hooks/useAgentHistory';
import type { HistorySession } from './types';

const cellStyle: React.CSSProperties = {
  padding: '6px 10px',
  borderBottom: `1px solid ${tokens.color.border}`,
  fontSize: 13,
  whiteSpace: 'nowrap',
};

const PAGE_SIZE_OPTIONS = [10, 20, 25, 50, 100];

// Past (not currently live) sessions. Two alternative views share this one component:
// by-project (the original, drill into one project directory's sessions) and by-recency (flat,
// most-recent-first across every project, paginated since the full list can be large).
// Selecting a session links into the same /agents/:sessionId route AgentsView does, so
// AgentPage's existing Session-tab transcript viewer (SessionTranscript, keyed only by session
// id) is reused as-is; no history-specific viewer needed. The Chat tab there assumes a live
// agent to DM, so it's meaningless for a past session -- AgentPage already defaults to the
// Session tab, which is what matters here.
export default function AgentHistoryView() {
  const { project } = useParams<{ project?: string }>();
  const navigate = useNavigate();
  const loc = useLocation();

  if (loc.pathname === '/agents/history/recent') {
    return <RecencyView onBack={() => navigate('/agents/history')} />;
  }
  if (project === undefined) {
    return <ProjectPicker />;
  }
  return <SessionList project={project === 'all' ? null : decodeURIComponent(project)} onBack={() => navigate('/agents/history')} />;
}

function ViewTabs({ active }: { active: 'project' | 'recency' }) {
  const tabStyle = (isActive: boolean): React.CSSProperties => ({
    padding: '4px 10px',
    borderRadius: 6,
    fontSize: 13,
    textDecoration: 'none',
    color: isActive ? tokens.color.text : tokens.color.textMuted,
    background: isActive ? tokens.color.border : 'transparent',
  });
  return (
    <div style={{ display: 'flex', gap: 4 }}>
      <Link to="/agents/history" style={tabStyle(active === 'project')}>
        By Project
      </Link>
      <Link to="/agents/history/recent" style={tabStyle(active === 'recency')}>
        By Recency
      </Link>
    </div>
  );
}

function ProjectPicker() {
  const { projects, isLoading, error } = useAgentHistoryProjects();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Header title="Past Sessions" />
      <ViewTabs active="project" />
      {error && <p style={{ margin: 0, color: tokens.color.danger }}>{error}</p>}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <ProjectLink label="All projects" project="all" />
        {projects.map((p) => (
          <ProjectLink key={p.project} label={p.project} project={p.project} sessionCount={p.session_count} />
        ))}
      </div>
      {!error && (
        <p style={{ margin: 0, color: tokens.color.textMuted, fontSize: 13 }}>
          {isLoading ? 'Loading projects…' : projects.length === 0 ? 'No past sessions found.' : null}
        </p>
      )}
    </div>
  );
}

function ProjectLink({ label, project, sessionCount }: { label: string; project: string; sessionCount?: number }) {
  return (
    <Link
      to={`/agents/history/${encodeURIComponent(project)}`}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '6px 10px',
        color: tokens.color.text,
        textDecoration: 'none',
        fontSize: 13,
      }}
    >
      {sessionCount !== undefined && (
        <span style={{ color: tokens.color.textMuted, minWidth: 40, textAlign: 'right' }}>{sessionCount}</span>
      )}
      <span style={{ fontFamily: project === 'all' ? undefined : 'monospace' }}>{label}</span>
    </Link>
  );
}

function SessionList({ project, onBack }: { project: string | null; onBack: () => void }) {
  const { sessions, isLoading, error } = useAgentHistorySessions(project);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Header title={project ?? 'All projects'} onBack={onBack} monospaceTitle={project !== null} />
      <ViewTabs active="project" />
      {error && <p style={{ margin: 0, color: tokens.color.danger }}>{error}</p>}
      <SessionTable sessions={sessions} showProject={project === null} isLoading={isLoading} />
    </div>
  );
}

// Flat view across every project, sorted most-recent-first (the API's own sort order, see
// list_history_sessions), paginated client-side since the full cross-project list can be long
// and we don't want to render it all at once.
function RecencyView({ onBack }: { onBack: () => void }) {
  const { sessions, isLoading, error } = useAgentHistorySessions(null);
  const [pageSize, setPageSize] = useState(PAGE_SIZE_OPTIONS[0]);
  const [page, setPage] = useState(0);

  const pageCount = Math.max(1, Math.ceil(sessions.length / pageSize));
  const clampedPage = Math.min(page, pageCount - 1);
  const pageSessions = useMemo(
    () => sessions.slice(clampedPage * pageSize, clampedPage * pageSize + pageSize),
    [sessions, clampedPage, pageSize],
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Header title="All projects (by recency)" onBack={onBack} />
      <ViewTabs active="recency" />
      {error && <p style={{ margin: 0, color: tokens.color.danger }}>{error}</p>}
      <SessionTable sessions={pageSessions} showProject isLoading={isLoading} />
      {!error && sessions.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 13, color: tokens.color.textMuted }}>
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={clampedPage === 0}
            style={pagerButtonStyle}
          >
            ← Prev
          </button>
          <span>
            Page {clampedPage + 1} of {pageCount} ({sessions.length} sessions)
          </span>
          <button
            type="button"
            onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
            disabled={clampedPage >= pageCount - 1}
            style={pagerButtonStyle}
          >
            Next →
          </button>
          <label style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
            Per page
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(0);
              }}
              style={{
                fontSize: 13,
                padding: '2px 6px',
                borderRadius: 4,
                border: `1px solid ${tokens.color.border}`,
                background: 'transparent',
                color: tokens.color.text,
              }}
            >
              {PAGE_SIZE_OPTIONS.map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}
    </div>
  );
}

const pagerButtonStyle: React.CSSProperties = {
  background: 'none',
  border: `1px solid ${tokens.color.border}`,
  borderRadius: 4,
  color: tokens.color.text,
  fontSize: 13,
  cursor: 'pointer',
  padding: '2px 8px',
};

function SessionTable({
  sessions,
  showProject,
  isLoading,
}: {
  sessions: HistorySession[];
  showProject: boolean;
  isLoading: boolean;
}) {
  return (
    <div style={{ overflowX: 'auto', border: `1px solid ${tokens.color.border}`, borderRadius: 8 }}>
      <table style={{ borderCollapse: 'collapse', width: '100%' }}>
        <thead>
          <tr>
            {['Session', 'Messages', 'Date', ...(showProject ? ['Project'] : [])].map((header) => (
              <th key={header} style={{ ...cellStyle, textAlign: 'left', color: tokens.color.textMuted, fontWeight: 500 }}>
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sessions.map((session) => (
            <SessionRow key={session.id} session={session} showProject={showProject} />
          ))}
        </tbody>
      </table>
      {isLoading || sessions.length === 0 ? (
        <p style={{ margin: 0, padding: 12, color: tokens.color.textMuted, fontSize: 13 }}>
          {isLoading ? 'Loading sessions…' : 'No sessions found.'}
        </p>
      ) : null}
    </div>
  );
}

function SessionRow({ session, showProject }: { session: HistorySession; showProject: boolean }) {
  return (
    <tr>
      <td style={cellStyle}>
        <Link
          to={`/agents/${encodeURIComponent(session.id)}`}
          state={{ fromHistoryProject: session.project }}
          title={session.id}
          style={{ color: 'inherit', textDecoration: 'none' }}
        >
          {session.title || session.id}
        </Link>
      </td>
      <td style={cellStyle}>{session.message_count}</td>
      <td style={cellStyle}>{session.timestamp.slice(0, 16).replace('T', ' ')}</td>
      {showProject && <td style={{ ...cellStyle, fontFamily: 'monospace' }}>{session.project}</td>}
    </tr>
  );
}

function Header({ title, onBack, monospaceTitle }: { title: string; onBack?: () => void; monospaceTitle?: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      {onBack && (
        <button
          type="button"
          onClick={onBack}
          style={{
            background: 'none',
            border: 'none',
            color: tokens.color.textMuted,
            fontSize: 13,
            cursor: 'pointer',
            padding: 0,
          }}
        >
          ← Projects
        </button>
      )}
      <h1 style={{ margin: 0, fontSize: 18, fontFamily: monospaceTitle ? 'monospace' : undefined }}>{title}</h1>
    </div>
  );
}
