"""After any `kb` command creates a record with an embedding, name the closest existing records of
the same type, so a duplicate is noticed when it is made rather than later.

Structural rather than per-command: `track_new_records` hooks the CLI session's flushes, so every
`add`-style command (and any added later) is covered without calling anything itself.

The notice goes to stderr: stdout is a command's result, and a caller that reads it (a
`kb hooks` adapter, for which any stdout is a block reason or hint, or a script capturing an
`add`'s output) must get only that.
"""

import sys

from sqlalchemy import event
from sqlalchemy.orm import Session

from models.behaviors.embedding import HasEmbedding

# Cosine distance under which an existing record is worth a look. Calibrated 2026-10-15 on 247
# pending Todos: the one true duplicate pair sat at 0.0, closely related pairs at 0.15-0.25, the
# median nearest neighbor at 0.47; 10% had a neighbor under 0.294 and 20% under 0.371. A
# title-only restatement of a Todo with long notes measured 0.303, so the cutoff sits above it.
SIMILAR_DISTANCE = 0.35
_MAX_RECORDS = 3
_MAX_MATCHES = 2
_INFO_KEY = "kb_new_embedded_records"


def track_new_records(session: Session) -> None:
    """Remember every HasEmbedding record this session inserts, for print_similar."""
    created: list[HasEmbedding] = session.info.setdefault(_INFO_KEY, [])

    @event.listens_for(session, "after_flush")
    def _collect(flushed: Session, _context: object) -> None:
        created.extend(obj for obj in flushed.new if isinstance(obj, HasEmbedding))


def similar_records(session: Session, record: HasEmbedding) -> list[tuple[HasEmbedding, float]]:
    """Existing records of record's own type within SIMILAR_DISTANCE of it, closest first."""
    if not record.embedding:
        return []
    matches = type(record).search(session, "", limit=_MAX_MATCHES + 1, vec=record.embedding)
    return [(row, dist) for row, dist in matches if row.id != record.id and dist < SIMILAR_DISTANCE][:_MAX_MATCHES]


def print_similar(session: Session) -> None:
    """For each record tracked by track_new_records (the first few), print its close matches."""
    created: list[HasEmbedding] = session.info.get(_INFO_KEY, [])
    seen: set[tuple[str, int]] = set()
    for record in created:
        key = (type(record).__name__, record.id)
        if key in seen or getattr(record, "deleted_at", None) is not None:
            continue
        seen.add(key)
        if len(seen) > _MAX_RECORDS:
            break
        for row, dist in similar_records(session, record):
            title = getattr(row, "title", None) or getattr(row, "name", None) or ""
            print(f"similar existing {key[0]} #{row.id} {title!r} (dist={dist:.2f}) -- same record?", file=sys.stderr)
