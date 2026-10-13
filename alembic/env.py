import os
import shutil
import sys
from datetime import datetime, timezone
from logging.config import fileConfig
from pathlib import Path

import psutil
from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

_DB_PATH = Path(__file__).parent.parent / "data" / "kb.db"
config.set_main_option("sqlalchemy.url", f"sqlite:///{_DB_PATH}")

from base import Base  # noqa: E402
import models  # noqa: E402,F401 — import needed so all Base subclasses register
import models_pg  # noqa: E402,F401 — every domain module must be imported so its tables are known to Base.metadata

target_metadata = Base.metadata


def _backup_db() -> None:
    if not _DB_PATH.exists():
        return
    backup_dir = _DB_PATH.parent / "backups"
    backup_dir.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = backup_dir / f"kb_{timestamp}.db"
    shutil.copy2(_DB_PATH, dest)
    print(f"[alembic] Backed up db to {dest}")


def _db_holders() -> list[psutil.Process]:
    """Every other process with the database (or its WAL file) open."""
    paths = {str(_DB_PATH.resolve()), f"{_DB_PATH.resolve()}-wal"}
    holders = []
    for proc in psutil.process_iter():
        if proc.pid == os.getpid():
            continue
        try:
            if any(f.path in paths for f in proc.open_files()):
                holders.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return holders


def _refuse_if_db_open() -> None:
    """Refuse to change the schema while another process has the database open. SQLite
    commits each DDL statement as it runs under Python's sqlite3 driver, so a process
    reading during a migration can see new columns before the migration has filled them in,
    and act on that half-migrated state."""
    cmd = getattr(config.cmd_opts, "cmd", None)
    if not cmd or cmd[0].__name__ not in ("upgrade", "downgrade"):
        return
    holders = _db_holders()
    if not holders:
        return
    lines = []
    for proc in holders:
        try:
            lines.append(f"  pid {proc.pid}: {' '.join(proc.cmdline())}")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            lines.append(f"  pid {proc.pid}")
    sys.exit(
        f"Refusing to migrate: {_DB_PATH} is open in another process. Stop these, then rerun:\n" + "\n".join(lines)
    )


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    _backup_db()
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    _refuse_if_db_open()
    _backup_db()
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
