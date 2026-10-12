"""harness_session: integer key, harness's own id moves to harness_id

Revision ID: a3c91e7d4b20
Revises: 5eb3fe6a2cb0
Create Date: 2026-10-12 14:05:00

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a3c91e7d4b20'
down_revision: Union[str, Sequence[str], None] = '5eb3fe6a2cb0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Raw-SQL table recreate (see 752237ed2641 for why not batch mode). harness_session gets an
# integer primary key, its old string key becomes harness_id, and the three channel tables'
# session columns are remapped from the string to the new integer through a join. All four
# new tables are created and filled before any old table is dropped, and the old tables are
# dropped rather than renamed, so no foreign key clause is rewritten by SQLite's RENAME.

_HARNESS_SESSION = """
    CREATE TABLE harness_session_new (
        id INTEGER NOT NULL,
        harness_id VARCHAR NOT NULL,
        cwd VARCHAR NOT NULL,
        title VARCHAR,
        pid INTEGER NOT NULL,
        kind VARCHAR(5) NOT NULL,
        status VARCHAR(9) NOT NULL,
        is_listening BOOLEAN NOT NULL,
        listener_pid INTEGER,
        last_active_at DATETIME,
        last_response_at DATETIME,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        deleted_at DATETIME,
        CONSTRAINT pk_harness_session PRIMARY KEY (id),
        CONSTRAINT uq_harness_session_harness_id UNIQUE (harness_id),
        CONSTRAINT ck_harness_session_harnesssessionkind CHECK (kind IN ('AGENT', 'HUMAN')),
        CONSTRAINT ck_harness_session_harnesssessionstatus CHECK (status IN ('INFERRING', 'IDLE'))
    )
"""

_UP = [
    _HARNESS_SESSION,
    """
    INSERT INTO harness_session_new (harness_id, cwd, title, pid, kind, status, is_listening, listener_pid,
        last_active_at, last_response_at, created_at, updated_at, deleted_at)
    SELECT id, cwd, title, pid, kind, status, is_listening, listener_pid,
        last_active_at, last_response_at, created_at, updated_at, deleted_at
    FROM harness_session ORDER BY created_at, id
    """,
    """
    CREATE TABLE channel_subscription_new (
        id INTEGER NOT NULL,
        channel_id INTEGER NOT NULL,
        session_id INTEGER NOT NULL,
        subscribed_at DATETIME NOT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        deleted_at DATETIME,
        CONSTRAINT pk_channel_subscription PRIMARY KEY (id),
        CONSTRAINT uq_channel_subscription UNIQUE (channel_id, session_id),
        CONSTRAINT fk_channel_subscription_channel_id_channel FOREIGN KEY(channel_id) REFERENCES channel (id),
        CONSTRAINT fk_channel_subscription_session_id_harness_session FOREIGN KEY(session_id) REFERENCES harness_session (id)
    )
    """,
    """
    INSERT INTO channel_subscription_new
    SELECT s.id, s.channel_id, h.id, s.subscribed_at, s.created_at, s.updated_at, s.deleted_at
    FROM channel_subscription s JOIN harness_session_new h ON h.harness_id = s.session_id
    """,
    """
    CREATE TABLE channel_message_new (
        id INTEGER NOT NULL,
        channel_id INTEGER NOT NULL,
        from_session INTEGER NOT NULL,
        body TEXT NOT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        deleted_at DATETIME,
        CONSTRAINT pk_channel_message PRIMARY KEY (id),
        CONSTRAINT fk_channel_message_channel_id_channel FOREIGN KEY(channel_id) REFERENCES channel (id),
        CONSTRAINT fk_channel_message_from_session_harness_session FOREIGN KEY(from_session) REFERENCES harness_session (id)
    )
    """,
    """
    INSERT INTO channel_message_new
    SELECT m.id, m.channel_id, h.id, m.body, m.created_at, m.updated_at, m.deleted_at
    FROM channel_message m JOIN harness_session_new h ON h.harness_id = m.from_session
    """,
    """
    CREATE TABLE channel_read_new (
        id INTEGER NOT NULL,
        channel_id INTEGER NOT NULL,
        session_id INTEGER NOT NULL,
        read_at DATETIME NOT NULL,
        up_to_message_id INTEGER NOT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        deleted_at DATETIME,
        CONSTRAINT pk_channel_read PRIMARY KEY (id),
        CONSTRAINT fk_channel_read_channel_id_channel FOREIGN KEY(channel_id) REFERENCES channel (id),
        CONSTRAINT fk_channel_read_session_id_harness_session FOREIGN KEY(session_id) REFERENCES harness_session (id),
        CONSTRAINT fk_channel_read_up_to_message_id_channel_message FOREIGN KEY(up_to_message_id) REFERENCES channel_message (id)
    )
    """,
    """
    INSERT INTO channel_read_new
    SELECT r.id, r.channel_id, h.id, r.read_at, r.up_to_message_id, r.created_at, r.updated_at, r.deleted_at
    FROM channel_read r JOIN harness_session_new h ON h.harness_id = r.session_id
    """,
    "DROP TABLE channel_read",
    "DROP TABLE channel_message",
    "DROP TABLE channel_subscription",
    "DROP TABLE harness_session",
    "ALTER TABLE harness_session_new RENAME TO harness_session",
    "ALTER TABLE channel_subscription_new RENAME TO channel_subscription",
    "ALTER TABLE channel_message_new RENAME TO channel_message",
    "ALTER TABLE channel_read_new RENAME TO channel_read",
]

_DOWN = [
    """
    CREATE TABLE harness_session_old (
        id VARCHAR NOT NULL,
        cwd VARCHAR NOT NULL,
        title VARCHAR,
        pid INTEGER NOT NULL,
        kind VARCHAR(5) NOT NULL,
        status VARCHAR(9) NOT NULL,
        is_listening BOOLEAN NOT NULL,
        listener_pid INTEGER,
        last_active_at DATETIME,
        last_response_at DATETIME,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        deleted_at DATETIME,
        CONSTRAINT pk_harness_session PRIMARY KEY (id),
        CONSTRAINT ck_harness_session_harnesssessionkind CHECK (kind IN ('AGENT', 'HUMAN')),
        CONSTRAINT ck_harness_session_harnesssessionstatus CHECK (status IN ('INFERRING', 'IDLE'))
    )
    """,
    """
    INSERT INTO harness_session_old
    SELECT harness_id, cwd, title, pid, kind, status, is_listening, listener_pid,
        last_active_at, last_response_at, created_at, updated_at, deleted_at
    FROM harness_session
    """,
    """
    CREATE TABLE channel_subscription_old (
        id INTEGER NOT NULL,
        channel_id INTEGER NOT NULL,
        session_id VARCHAR NOT NULL,
        subscribed_at DATETIME NOT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        deleted_at DATETIME,
        CONSTRAINT pk_channel_subscription PRIMARY KEY (id),
        CONSTRAINT uq_channel_subscription UNIQUE (channel_id, session_id),
        CONSTRAINT fk_channel_subscription_channel_id_channel FOREIGN KEY(channel_id) REFERENCES channel (id),
        CONSTRAINT fk_channel_subscription_session_id_harness_session FOREIGN KEY(session_id) REFERENCES harness_session (id)
    )
    """,
    """
    INSERT INTO channel_subscription_old
    SELECT s.id, s.channel_id, h.harness_id, s.subscribed_at, s.created_at, s.updated_at, s.deleted_at
    FROM channel_subscription s JOIN harness_session h ON h.id = s.session_id
    """,
    """
    CREATE TABLE channel_message_old (
        id INTEGER NOT NULL,
        channel_id INTEGER NOT NULL,
        from_session VARCHAR NOT NULL,
        body TEXT NOT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        deleted_at DATETIME,
        CONSTRAINT pk_channel_message PRIMARY KEY (id),
        CONSTRAINT fk_channel_message_channel_id_channel FOREIGN KEY(channel_id) REFERENCES channel (id),
        CONSTRAINT fk_channel_message_from_session_harness_session FOREIGN KEY(from_session) REFERENCES harness_session (id)
    )
    """,
    """
    INSERT INTO channel_message_old
    SELECT m.id, m.channel_id, h.harness_id, m.body, m.created_at, m.updated_at, m.deleted_at
    FROM channel_message m JOIN harness_session h ON h.id = m.from_session
    """,
    """
    CREATE TABLE channel_read_old (
        id INTEGER NOT NULL,
        channel_id INTEGER NOT NULL,
        session_id VARCHAR NOT NULL,
        read_at DATETIME NOT NULL,
        up_to_message_id INTEGER NOT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        deleted_at DATETIME,
        CONSTRAINT pk_channel_read PRIMARY KEY (id),
        CONSTRAINT fk_channel_read_channel_id_channel FOREIGN KEY(channel_id) REFERENCES channel (id),
        CONSTRAINT fk_channel_read_session_id_harness_session FOREIGN KEY(session_id) REFERENCES harness_session (id),
        CONSTRAINT fk_channel_read_up_to_message_id_channel_message FOREIGN KEY(up_to_message_id) REFERENCES channel_message (id)
    )
    """,
    """
    INSERT INTO channel_read_old
    SELECT r.id, r.channel_id, h.harness_id, r.read_at, r.up_to_message_id, r.created_at, r.updated_at, r.deleted_at
    FROM channel_read r JOIN harness_session h ON h.id = r.session_id
    """,
    "DROP TABLE channel_read",
    "DROP TABLE channel_message",
    "DROP TABLE channel_subscription",
    "DROP TABLE harness_session",
    "ALTER TABLE harness_session_old RENAME TO harness_session",
    "ALTER TABLE channel_subscription_old RENAME TO channel_subscription",
    "ALTER TABLE channel_message_old RENAME TO channel_message",
    "ALTER TABLE channel_read_old RENAME TO channel_read",
]


def upgrade() -> None:
    for statement in _UP:
        op.execute(statement)


def downgrade() -> None:
    for statement in _DOWN:
        op.execute(statement)
