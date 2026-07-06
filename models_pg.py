"""Project Gorgon-specific tables. Separated from models.py since this is a large, rarely-needed
chunk when working on kb's shared core — no universal/MMO base yet, see mixins.py docstring for
the layering rationale: start narrow at the game layer, generalize upward only once a second
game's real data proves something is actually shared."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from base import Base
from mixins import HasStackSize
from models import Item

class PgItem(Item, HasStackSize):
    """Project Gorgon items."""
    __tablename__ = "pg_item"

    id: Mapped[int] = mapped_column(Integer, ForeignKey("item.id"), primary_key=True)
    kind: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    sources: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __mapper_args__ = {"polymorphic_identity": "pg"}




class PgSkill(Base):
    __tablename__ = "pg_skill"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    def __repr__(self) -> str:
        return f"<PgSkill {self.name!r}>"


class PgCharacter(Base):
    """A character you (the player) control."""
    __tablename__ = "pg_character"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    race: Mapped[str] = mapped_column(Text, nullable=False)
    is_druid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_vampire: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    hangout_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("pg_hangout.id"), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    hangout: Mapped[Optional["PgHangout"]] = relationship("PgHangout")

    def __repr__(self) -> str:
        extras = "+".join(e for e, v in [("druid", self.is_druid), ("vampire", self.is_vampire)] if v)
        return f"<PgCharacter {self.name} {self.race}{' ' + extras if extras else ''}>"


class PgNpcRace(Base):
    __tablename__ = "pg_npc_race"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    def __repr__(self) -> str:
        return f"<PgNpcRace {self.name!r}>"


class PgNpc(Base):
    __tablename__ = "pg_npc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    race_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("pg_npc_race.id"), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    race: Mapped[Optional[PgNpcRace]] = relationship("PgNpcRace")

    def __repr__(self) -> str:
        return f"<PgNpc {self.name!r}>"


class PgNpcRelation(Base):
    __tablename__ = "pg_npc_relation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    character_id: Mapped[int] = mapped_column(Integer, ForeignKey("pg_character.id"), nullable=False)
    npc_id: Mapped[int] = mapped_column(Integer, ForeignKey("pg_npc.id"), nullable=False)
    favor: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    character: Mapped[PgCharacter] = relationship("PgCharacter")
    npc: Mapped[PgNpc] = relationship("PgNpc")

    def __repr__(self) -> str:
        return f"<PgNpcRelation {self.character.name if self.character else '?'} -> {self.npc.name if self.npc else '?'} [{self.favor}]>"


class PgQuest(Base):
    __tablename__ = "pg_quest"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    giver_npc_id: Mapped[int] = mapped_column(Integer, ForeignKey("pg_npc.id"), nullable=False)
    completion_npc_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("pg_npc.id"), nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="available")
    objectives: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rewards: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    giver: Mapped[PgNpc] = relationship("PgNpc", foreign_keys=[giver_npc_id])
    completion_npc: Mapped[Optional[PgNpc]] = relationship("PgNpc", foreign_keys=[completion_npc_id])

    def __repr__(self) -> str:
        return f"<PgQuest {self.title!r} [{self.status}]>"


class PgDungeon(Base):
    __tablename__ = "pg_dungeon"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    location: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    level_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    level_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    def __repr__(self) -> str:
        return f"<PgDungeon {self.name!r}>"


class PgMob(Base):
    """A killable enemy, distinct from PgNpc (interactable: trainer/shop/quest-giver/lore)."""
    __tablename__ = "pg_mob"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    location: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    def __repr__(self) -> str:
        return f"<PgMob {self.name!r}>"


class PgMobDrop(Base):
    __tablename__ = "pg_mob_drop"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mob_id: Mapped[int] = mapped_column(Integer, ForeignKey("pg_mob.id"), nullable=False)
    item_id: Mapped[int] = mapped_column(Integer, ForeignKey("pg_item.id"), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    mob: Mapped[PgMob] = relationship("PgMob")
    item: Mapped["PgItem"] = relationship("PgItem")

    def __repr__(self) -> str:
        return f"<PgMobDrop {self.mob.name if self.mob else '?'} -> {self.item.name if self.item else '?'}>"


class PgHangout(Base):
    """A definition: what an NPC's hangout gives, not a per-character instance. A character has at
    most one active hangout at a time (PgCharacter.hangout_id) -- its timer runs while logged out,
    and rewards are granted on next login once duration_minutes has elapsed since logout. Exact
    remaining-time tracking is deliberately not modeled; duration is fixed/canonical per hangout,
    never randomized."""
    __tablename__ = "pg_hangout"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    npc_id: Mapped[int] = mapped_column(Integer, ForeignKey("pg_npc.id"), nullable=False)
    favor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skill_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("pg_skill.id"), nullable=True)
    skill_xp: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    is_repeatable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    npc: Mapped[PgNpc] = relationship("PgNpc")
    skill: Mapped[Optional[PgSkill]] = relationship("PgSkill")

    def __repr__(self) -> str:
        return f"<PgHangout {self.name!r} ({self.npc.name if self.npc else '?'})>"


class PgHangoutItem(Base):
    __tablename__ = "pg_hangout_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hangout_id: Mapped[int] = mapped_column(Integer, ForeignKey("pg_hangout.id"), nullable=False)
    item_id: Mapped[int] = mapped_column(Integer, ForeignKey("pg_item.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    hangout: Mapped[PgHangout] = relationship("PgHangout")
    item: Mapped["PgItem"] = relationship("PgItem")

    def __repr__(self) -> str:
        return f"<PgHangoutItem {self.hangout.name if self.hangout else '?'}: {self.quantity}x {self.item.name if self.item else '?'}>"


class PgPlayer(Base):
    """Another player's character you've encountered. One row per character name met —
    the same person under multiple aliases gets multiple rows, linked via notes."""
    __tablename__ = "pg_player"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    friendly: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    def __repr__(self) -> str:
        return f"<PgPlayer {self.name!r}{'' if self.friendly else ' [unfriendly]'}>"

