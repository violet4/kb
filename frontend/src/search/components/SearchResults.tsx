import { Link } from 'react-router-dom';
import { entityPath } from '../../entities/navigation';
import type { EntityType } from '../../entities/types';
import { tokens } from '../../shared/tokens';
import type { SearchHit } from '../types';

interface SearchResultsProps {
  hits: SearchHit[];
}

export default function SearchResults({ hits }: SearchResultsProps) {
  if (hits.length === 0) return null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {hits.map((hit) => (
        <SearchResultRow key={`${hit.type}:${hit.id}`} hit={hit} />
      ))}
    </div>
  );
}

function SearchResultRow({ hit }: { hit: SearchHit }) {
  const meta = `${hit.type}:${hit.id} · ${hit.is_substring ? 'substring' : `dist=${hit.dist.toFixed(3)}`}`;
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
    color: tokens.color.text,
    textDecoration: 'none',
  } as const;

  const body = hit.drilldown ? (
    <Link to={entityPath(hit.type as EntityType, hit.id)} style={style}>
      {content}
    </Link>
  ) : (
    <div style={style}>{content}</div>
  );

  if (!hit.original_url && !hit.archivebox_url) return body;
  return (
    <div>
      {body}
      <ArchivedLinkUrls originalUrl={hit.original_url} archiveboxUrl={hit.archivebox_url} />
    </div>
  );
}

function ArchivedLinkUrls({ originalUrl, archiveboxUrl }: { originalUrl: string | null; archiveboxUrl: string | null }) {
  return (
    <div style={{ display: 'flex', gap: 12, padding: '4px 10px', fontSize: 12 }}>
      {originalUrl && (
        <a href={originalUrl} target="_blank" rel="noreferrer" style={{ color: tokens.color.accent }}>
          original source
        </a>
      )}
      {archiveboxUrl && (
        <a href={archiveboxUrl} target="_blank" rel="noreferrer" style={{ color: tokens.color.accent }}>
          archivebox
        </a>
      )}
    </div>
  );
}
