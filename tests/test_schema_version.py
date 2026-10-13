"""schema_version reads the revision graph from the version files without alembic's script
directory, so its head must match alembic's, and pending_count must count exactly the
migrations between the database's stamp and that head."""

import sqlite3
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

import schema_version


def test_heads_match_alembic() -> None:
    alembic_heads = set(ScriptDirectory.from_config(Config(str(schema_version.ALEMBIC_INI))).get_heads())
    assert schema_version.code_heads(schema_version.revision_graph()) == alembic_heads


def _version(directory: Path, revision: str, down: str) -> None:
    (directory / f"{revision}_x.py").write_text(
        f"revision: str = '{revision}'\ndown_revision: Union[str, Sequence[str], None] = {down}\n"
    )


@pytest.fixture
def chain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    versions = tmp_path / "versions"
    versions.mkdir()
    _version(versions, "a1", "None")
    _version(versions, "b2", "'a1'")
    _version(versions, "c3", "'a1'")
    _version(versions, "d4", "('b2', 'c3')")  # a merge
    db = tmp_path / "kb.db"
    monkeypatch.setattr(schema_version, "_VERSIONS_DIR", versions)
    monkeypatch.setattr(schema_version, "DB_PATH", db)
    return db


def _stamp(db: Path, *revisions: str) -> None:
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)")
        conn.executemany("INSERT INTO alembic_version VALUES (?)", [(r,) for r in revisions])


def test_merge_head_is_the_only_head(chain: Path) -> None:
    assert schema_version.code_heads(schema_version.revision_graph()) == {"d4"}


def test_current_database_has_nothing_pending(chain: Path) -> None:
    _stamp(chain, "d4")
    assert schema_version.pending_count() == 0


def test_counts_migrations_behind_including_both_merge_parents(chain: Path) -> None:
    _stamp(chain, "a1")
    assert schema_version.pending_count() == 3


def test_never_migrated_database_has_everything_pending(chain: Path) -> None:
    assert schema_version.pending_count() == 4


def test_unknown_revision_counts_as_current(chain: Path) -> None:
    _stamp(chain, "zz9")
    assert schema_version.pending_count() == 0
