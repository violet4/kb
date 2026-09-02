import { Link, useNavigate, useParams } from 'react-router-dom';
import { tokens } from '../shared/tokens';
import { useAgentHistoryProjects, useAgentHistorySessions } from './hooks/useAgentHistory';
import type { HistorySession } from './types';

const cellStyle: React.CSSProperties = {
  padding: '6px 10px',
  borderBottom: `1px solid ${tokens.color.border}`,
  fontSize: 13,
  whiteSpace: 'nowrap',
};

// Past (not currently live) sessions, browsed by project directory -- the read-only
// counterpart to AgentsView's live table. Selecting a session links into the same
// /agents/:sessionId route AgentsView does, so AgentPage's existing Session-tab transcript
// viewer (SessionTranscript, keyed only by session id) is reused as-is; no history-specific
// viewer needed. The Chat tab there assumes a live agent to DM, so it's meaningless for a
// past session -- AgentPage already defaults to the Session tab, which is what matters here.
export default function AgentHistoryView() {
  const { project } = useParams<{ project?: string }>();
  const navigate = useNavigate();

  if (project === undefined) {
    return <ProjectPicker />;
  }
  return <SessionList project={project === 'all' ? null : decodeURIComponent(project)} onBack={() => navigate('/agents/history')} />;
}

function ProjectPicker() {
  const { projects, isLoading, error } = useAgentHistoryProjects();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Header title="Past Sessions" />
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
      {error && <p style={{ margin: 0, color: tokens.color.danger }}>{error}</p>}
      <div style={{ overflowX: 'auto', border: `1px solid ${tokens.color.border}`, borderRadius: 8 }}>
        <table style={{ borderCollapse: 'collapse', width: '100%' }}>
          <thead>
            <tr>
              {['Session', 'Messages', 'Date', ...(project === null ? ['Project'] : [])].map((header) => (
                <th
                  key={header}
                  style={{ ...cellStyle, textAlign: 'left', color: tokens.color.textMuted, fontWeight: 500 }}
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sessions.map((session) => (
              <SessionRow key={session.id} session={session} showProject={project === null} />
            ))}
          </tbody>
        </table>
        {!error && (isLoading || sessions.length === 0) && (
          <p style={{ margin: 0, padding: 12, color: tokens.color.textMuted, fontSize: 13 }}>
            {isLoading ? 'Loading sessions…' : 'No sessions found.'}
          </p>
        )}
      </div>
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
