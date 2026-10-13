import { Link } from 'react-router-dom';
import { entityPath } from '../../entities/navigation';
import type { EntityType } from '../../entities/types';
import { recordDragProps } from '../../shared/recordDrag';
import { tokens } from '../../shared/tokens';
import type { RecordHit, SearchHit } from '../types';

export default function SearchResults({ hits }: { hits: SearchHit[] }) {
  return (
    <RecordList hits={hits} describe={(hit) => (hit.is_substring ? 'substring' : `dist=${hit.dist.toFixed(3)}`)} />
  );
}

// Mixed-type records, one linked row each; describe adds to the row's TYPE:ID line.
export function RecordList<T extends RecordHit>({ hits, describe }: { hits: T[]; describe: (hit: T) => string }) {
  if (hits.length === 0) return null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {hits.map((hit) => (
        <RecordRow key={`${hit.type}:${hit.id}`} hit={hit} detail={describe(hit)} />
      ))}
    </div>
  );
}

function RecordRow({ hit, detail }: { hit: RecordHit; detail: string }) {
  const meta = `${hit.type}:${hit.id} · ${detail}`;
  const content = (
    <>
      <p style={{ margin: 0 }}>{hit.label}</p>
      <p style={{ margin: 0, fontSize: 12, color: tokens.color.textMuted }}>{meta}</p>
    </>
  );
  const style = {
    display: 'block',
    padding: '8px 10px',
    borderRadius: 4,
    border: `1px solid ${tokens.color.border}`,
    ...(hit.drilldown ? tokens.link : { color: tokens.color.text, textDecoration: 'none' }),
  } as const;

  const body = hit.drilldown ? (
    <Link to={entityPath(hit.type as EntityType, hit.id)} style={style} draggable={false}>
      {content}
    </Link>
  ) : (
    <div style={style}>{content}</div>
  );

  // A hit with a context can be dragged onto a context in the Contexts sidebar to move it there.
  const drag = hit.placement ? { ...recordDragProps({ type: hit.type, id: hit.id, label: hit.label }), style: { cursor: 'grab' } } : {};
  return (
    <div {...drag}>
      {body}
      {(hit.original_url || hit.archivebox_url) && (
        <ArchivedLinkUrls originalUrl={hit.original_url} archiveboxUrl={hit.archivebox_url} />
      )}
    </div>
  );
}

function ArchivedLinkUrls({ originalUrl, archiveboxUrl }: { originalUrl: string | null; archiveboxUrl: string | null }) {
  return (
    <div style={{ display: 'flex', gap: 12, padding: '4px 10px', fontSize: 12 }}>
      {originalUrl && (
        <a href={originalUrl} target="_blank" rel="noreferrer" style={tokens.link}>
          original source
        </a>
      )}
      {archiveboxUrl && (
        <a href={archiveboxUrl} target="_blank" rel="noreferrer" style={tokens.link}>
          archivebox
        </a>
      )}
    </div>
  );
}
