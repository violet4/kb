import { Link } from 'react-router-dom';
import { tokens } from '../../shared/tokens';
import { entityPath } from '../navigation';
import type { GraphNeighbor } from '../types';

interface GraphPanelProps {
  neighbors: GraphNeighbor[];
}

export default function GraphPanel({ neighbors }: GraphPanelProps) {
  if (neighbors.length === 0) return null;
  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <h2 style={{ margin: 0, fontSize: 15 }}>Links</h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {neighbors.map((n) => (
          <GraphNeighborRow key={n.link_id} neighbor={n} />
        ))}
      </div>
    </section>
  );
}

function GraphNeighborRow({ neighbor }: { neighbor: GraphNeighbor }) {
  const arrow = neighbor.direction === 'outgoing' ? '→' : '←';
  const label = `${arrow} ${neighbor.relation} ${arrow} ${neighbor.other_type}:${neighbor.other_id} ${neighbor.other_label}`;
  if (!neighbor.other_exists) {
    return (
      <p style={{ margin: 0, fontSize: 13, color: tokens.color.danger }}>
        {label} (missing)
      </p>
    );
  }
  return (
    <Link
      to={entityPath(neighbor.other_type as never, neighbor.other_id)}
      style={{ fontSize: 13, color: tokens.color.text, textDecoration: 'none' }}
    >
      {label}
    </Link>
  );
}
