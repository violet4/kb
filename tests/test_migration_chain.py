"""Every migration applies in order to an empty database, the path a new install's first server
start takes. A migration that only works against databases that already existed when it was
written (e.g. one querying through today's models) breaks new installs without failing
anything else, so this runs the whole chain in a subprocess against a throwaway database."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import schema_version


def test_full_chain_applies_to_an_empty_database(tmp_path: Path) -> None:
    db = tmp_path / "kb.db"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(schema_version.ALEMBIC_INI), "upgrade", "head"],
        cwd=schema_version.KB_DIR,
        env={**os.environ, "KB_DB_PATH": str(db)},
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stderr[-3000:]
    with sqlite3.connect(db) as conn:
        stamped = {row[0] for row in conn.execute("SELECT version_num FROM alembic_version")}
    assert stamped == schema_version.code_heads(schema_version.revision_graph())
