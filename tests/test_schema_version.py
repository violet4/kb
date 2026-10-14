"""schema_version reads the revision graph from the version files without alembic's script
directory, so its head must match alembic's, and pending_count must count exactly the
migrations between the database's stamp and that head."""

import sqlite3
import subprocess
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


def test_committed_graph_drops_uncommitted_and_what_follows(chain: Path) -> None:
    graph = schema_version.revision_graph()
    committed = schema_version.committed_graph(graph, {"c3"})
    assert set(committed) == {"a1", "b2"}  # d4 merges c3, so it waits too
    assert schema_version.code_heads(committed) == {"b2"}
    _stamp(chain, "a1")
    assert schema_version.pending_count(committed) == 1


def test_uncommitted_revisions_reads_git_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    versions = tmp_path / "alembic" / "versions"
    versions.mkdir(parents=True)
    _version(versions, "a1", "None")
    _version(versions, "b2", "'a1'")

    def run(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    run("init", "-q")
    run("add", "alembic/versions/a1_x.py")
    run("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "a1")
    monkeypatch.setattr(schema_version, "KB_DIR", tmp_path)
    monkeypatch.setattr(schema_version, "_VERSIONS_DIR", versions)
    assert schema_version.uncommitted_revisions() == {"b2"}  # untracked
    (versions / "a1_x.py").write_text((versions / "a1_x.py").read_text() + "# edited\n")
    assert schema_version.uncommitted_revisions() == {"a1", "b2"}  # modified, untracked
