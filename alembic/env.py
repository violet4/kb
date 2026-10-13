import shutil
import sys
from datetime import datetime, timezone
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    # Keep loggers configured before this ran: the server runs migrations in-process at
    # startup, and fileConfig's default would silence its loggers for the rest of its life.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

import schema_version  # noqa: E402

_DB_PATH = schema_version.DB_PATH
config.set_main_option("sqlalchemy.url", f"sqlite:///{_DB_PATH}")

from base import Base  # noqa: E402
import models  # noqa: E402,F401 — import needed so all Base subclasses register

_DB_CLOSE_TIMEOUT_SECONDS = 30

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


def _wait_until_db_closed() -> None:
    """Before an upgrade or downgrade, wait for other processes to close the database, and
    exit naming them if they have not within _DB_CLOSE_TIMEOUT_SECONDS. SQLite commits each
    DDL statement as it runs under Python's sqlite3 driver, so a process reading during a
    migration can see new columns before the migration has filled them in, and act on that
    half-migrated state. A call through alembic's Python API (the server's startup migration)
    has no command-line options and counts as an upgrade."""
    cmd = getattr(config.cmd_opts, "cmd", None)
    if cmd and cmd[0].__name__ not in ("upgrade", "downgrade"):
        return
    holders = schema_version.wait_until_db_closed(_DB_CLOSE_TIMEOUT_SECONDS)
    if holders:
        sys.exit(
            f"Refusing to migrate: {_DB_PATH} is still open in another process after "
            f"{_DB_CLOSE_TIMEOUT_SECONDS} s. Stop these, then rerun:\n"
            + "\n".join(f"  {schema_version.describe(proc)}" for proc in holders)
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
    _wait_until_db_closed()
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
