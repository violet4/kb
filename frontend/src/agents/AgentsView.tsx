import { Link } from 'react-router-dom';
import { tokens } from '../shared/tokens';
import { useAgentSessions } from './hooks/useAgentSessions';
import { useRefreshIntervalSetting } from './hooks/useRefreshIntervalSetting';
import type { AgentSession } from './types';

function formatSeconds(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s}s`;
  const minutes = Math.floor(s / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.floor(hours / 24)}d`;
}

const cellStyle: React.CSSProperties = {
  padding: '6px 10px',
  borderBottom: `1px solid ${tokens.color.border}`,
  fontSize: 13,
  whiteSpace: 'nowrap',
};

function Row({ session }: { session: AgentSession }) {
  return (
    <tr style={{ color: session.is_self ? tokens.color.accent : tokens.color.text }}>
      <td style={cellStyle}>
        <Link
          to={`/agents/${encodeURIComponent(session.id)}`}
          aria-label={`View chat for session ${session.id}`}
          style={{ color: 'inherit', textDecoration: 'none' }}
        >
          {session.id}
        </Link>
        {session.is_self && ' (you)'}
      </td>
      <td style={cellStyle}>{session.status}</td>
      <td style={cellStyle}>{session.listening || '—'}</td>
      <td style={cellStyle}>{formatSeconds(session.age_seconds)}</td>
      <td style={cellStyle}>{session.last_message_seconds !== null ? formatSeconds(session.last_message_seconds) : '—'}</td>
      <td style={cellStyle}>{session.cwd}</td>
      <td style={{ ...cellStyle, whiteSpace: 'normal' }}>{session.title || '—'}</td>
    </tr>
  );
}

function SettingsSection({
  intervalMs,
  onChangeIntervalMs,
}: {
  intervalMs: number;
  onChangeIntervalMs: (value: number) => void;
}) {
  return (
    <details style={{ fontSize: 13, color: tokens.color.textMuted }}>
      <summary style={{ cursor: 'pointer' }}>Settings</summary>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
        <label htmlFor="refresh-interval">Refresh interval (ms)</label>
        <input
          id="refresh-interval"
          type="number"
          min={200}
          step={100}
          value={intervalMs}
          onChange={(e) => {
            const value = Number(e.target.value);
            if (value > 0) onChangeIntervalMs(value);
          }}
          style={{
            width: 90,
            padding: '4px 8px',
            borderRadius: 6,
            border: `1px solid ${tokens.color.border}`,
            background: tokens.color.surface,
            color: tokens.color.text,
          }}
        />
      </div>
    </details>
  );
}

export default function AgentsView() {
  const [intervalMs, setIntervalMs] = useRefreshIntervalSetting();
  const { sessions, error } = useAgentSessions(intervalMs);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <h1 style={{ margin: 0, fontSize: 20 }}>Agents</h1>
        <SettingsSection intervalMs={intervalMs} onChangeIntervalMs={setIntervalMs} />
      </div>
      {error && <p style={{ margin: 0, color: tokens.color.danger }}>{error}</p>}
      <div style={{ overflowX: 'auto', border: `1px solid ${tokens.color.border}`, borderRadius: 8 }}>
        <table style={{ borderCollapse: 'collapse', width: '100%' }}>
          <thead>
            <tr>
              {['Session', 'Status', 'Listening', 'Age', 'Last Msg', 'Cwd', 'Title'].map((header) => (
                <th
                  key={header}
                  style={{
                    ...cellStyle,
                    textAlign: 'left',
                    color: tokens.color.textMuted,
                    fontWeight: 500,
                  }}
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sessions.map((session) => (
              <Row key={session.id} session={session} />
            ))}
          </tbody>
        </table>
        {sessions.length === 0 && !error && (
          <p style={{ margin: 0, padding: 12, color: tokens.color.textMuted, fontSize: 13 }}>No live sessions.</p>
        )}
      </div>
    </div>
  );
}
