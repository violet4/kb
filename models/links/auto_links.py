"""HasAutoLinks: EntityLinks kept in sync with the record references in a row's text."""

from __future__ import annotations

import re
from typing import Any, Optional, Sequence

from sqlalchemy import event, inspect
from sqlalchemy.orm import Mapped, Session, UOWTransaction

from models import flush_pending
from models.behaviors.embedding import HasEmbedding
from models.links.entity_link import EntityLink

_ENTITY_REF_RELATION = "mentions"


# Every prose spelling of an entity reference actually in use across kb -- not just the
# TYPE:ID form `kb link add` takes. `kb`'s own CLI output prints bare "#ID" (type implied
# by the command's own context) and prose (including this assistant's own replies) says
# "Note #343"/"Goal #14" as often as "Note:343" -- so all three separators (":", " #", "#")
# are real, existing spellings, not a hypothetical grammar. ArchivedLink is additionally
# referenced as "ABnnn" (no separator, no space) -- its own display prefix, not its class
# name -- established well before this mixin existed (see `kb ab add`'s own printed output),
# so it is special-cased via _ENTITY_REF_ALIASES rather than invented here.
_entity_ref_re = re.compile(r"\b([A-Z][A-Za-z]*)\s?#(\d+)\b|\b([A-Z][A-Za-z]*):(\d+)\b|\bAB(\d+)\b")


# Short display-prefix -> real model (__name__) aliases, for a type spelled by something
# other than its own class name. Checked in resolve/sync_auto_links, not baked into the
# regex groups above, so adding a new alias never means touching the regex again.
_ENTITY_REF_ALIASES = {"AB": "ArchivedLink"}


def _parse_entity_refs(text: str) -> set[tuple[str, int]]:
    """Every TYPE:ID / TYPE #ID / TYPE#ID / ABnnn reference in free text, as (type, id)
    pairs with aliases already resolved (e.g. "AB23" -> ("ArchivedLink", 23)). The one
    place this grammar is parsed -- HasAutoLinks.sync_auto_links is its only caller today,
    but any future reader (a CLI command resolving refs in stored text, a report) should
    call this rather than re-deriving the regex."""
    found: set[tuple[str, int]] = set()
    for type_a, id_a, type_b, id_b, ab_id in _entity_ref_re.findall(text):
        if ab_id:
            found.add(("ArchivedLink", int(ab_id)))
        else:
            entity_type, entity_id = (type_a, id_a) if type_a else (type_b, id_b)
            found.add((_ENTITY_REF_ALIASES.get(entity_type, entity_type), int(entity_id)))
    return found


class HasAutoLinks:
    """Auto-creates EntityLink rows (relation="mentions") for every TYPE:ID reference
    (e.g. "Todo:102") found in a subclass's own free-text fields -- the automatic
    counterpart to `kb link add`, which remains for any relation other than a bare
    mention. Subclasses implement `_link_fields()` (which columns to scan) and get
    auto-linking for free via the before_flush listener below, the same shape
    HasEmbedding uses for auto-reembedding. Only "mentions"-relation links are
    managed here: a manually created link with a different relation touching the
    same pair is left untouched, and a "mentions" link is removed if its source
    token is later edited out of the text (so links don't outlive the reference
    that created them), but a manually-created "mentions" link (if anyone ever adds
    one by hand) is never distinguished from an automatic one, so editing text that
    used to reference it will remove it same as any other -- there is no separate
    "auto" flag on EntityLink itself. EntityLink itself is defined later in this
    file; referenced here only inside method bodies, resolved at call time, not at
    class-definition time, so the forward reference is safe.

    A ref to an unknown type or nonexistent id is silently skipped (not an error) --
    free text is not a validated form, and a typo like "Note:99999" shouldn't block
    a save.

    _link_fields()/_link_source_text() default to whatever HasEmbedding's own
    _embed_fields()/_embed_source_text() already say for a model combining both
    mixins (the common case: the free-text fields worth semantically searching are
    the same ones worth scanning for references) -- a subclass overrides only when
    linking should scan a different field set than embedding does. This is a
    structural default, not a per-model opt-in list: a new HasAutoLinks subclass
    that also has HasEmbedding gets correct behavior with no extra step to
    remember, per kb instructions #15 (brittle-forgettable-defaults) -- the
    original design required every subclass to separately alias these two methods
    to HasEmbedding's, an exclusion-list-shaped gap were a future subclass to omit
    it, since the failure (NotImplementedError) would only surface at first write,
    not at class-definition time."""

    __tablename__: str
    id: Mapped[int]

    def _link_fields(self) -> set[str]:
        if isinstance(self, HasEmbedding):
            return self._embed_fields()
        raise NotImplementedError(f"{type(self).__name__} must override _link_fields()")

    def _link_source_text(self) -> str:
        if isinstance(self, HasEmbedding):
            return self._embed_source_text()
        raise NotImplementedError(f"{type(self).__name__} must override _link_source_text()")

    def sync_auto_links(self, session: Session) -> None:
        entity_type = type(self).__name__
        found = _parse_entity_refs(self._link_source_text())
        # Drop a self-reference -- "Todo:102" appearing in Todo 102's own text isn't a link.
        found.discard((entity_type, self.id))

        existing = {
            (link.other_side(entity_type, self.id), link)
            for link in EntityLink.for_entity(session, entity_type, self.id)
            if link.relation == _ENTITY_REF_RELATION
        }
        existing_refs = {ref for ref, _link in existing}

        for other_type, other_id in found - existing_refs:
            if EntityLink.resolve(session, other_type, other_id) is None:
                continue
            link = EntityLink(
                type_a=entity_type,
                id_a=self.id,
                type_b=other_type,
                id_b=other_id,
                relation=_ENTITY_REF_RELATION,
            )
            session.add(link)

        for ref, link in existing:
            if ref not in found:
                session.delete(link)


@event.listens_for(Session, "before_flush")
def _collect_auto_link_candidates(
    session: Session, flush_context: UOWTransaction, instances: Optional[Sequence[Any]]
) -> None:
    # Collect here (before PKs are necessarily assigned for new rows) but act in
    # after_flush, once every row -- including a brand-new HasAutoLinks instance --
    # has a real primary key. A nested session.flush() from inside before_flush
    # itself raises "Session is already flushing", which is why this can't just
    # flush-then-sync in place the way HasEmbedding's reembed (no PK needed) does.
    for obj in list(session.new) + list(session.dirty):
        if isinstance(obj, HasAutoLinks):
            state = inspect(obj)
            assert state is not None
            changed = {attr.key for attr in state.attrs if attr.history.has_changes()}
            if obj in session.new or changed & obj._link_fields():
                flush_pending.queue(session, "auto_links").append(obj)


@event.listens_for(Session, "after_flush")
def _sync_auto_links_dirty(session: Session, flush_context: UOWTransaction) -> None:
    for obj in flush_pending.take(session, "auto_links"):
        obj.sync_auto_links(session)
