"""SQLite schema migrations for Cognex."""

import logging
from sqlite3 import Connection

logger = logging.getLogger(__name__)

# Each migration: (version, description, sql_statements)
MIGRATIONS: list[tuple[int, str, list[str]]] = [
    (1, "initial schema", []),  # baseline
    (
        2,
        "add relevance_score to memories",
        [
            "ALTER TABLE memories ADD COLUMN relevance_score REAL DEFAULT 1.0",
        ],
    ),
    (
        3,
        "add tier to memories",
        [
            "ALTER TABLE memories ADD COLUMN tier INTEGER DEFAULT 2",
        ],
    ),
    (
        4,
        "add last_accessed to memories",
        [
            "ALTER TABLE memories ADD COLUMN last_accessed TEXT",
        ],
    ),
    (
        5,
        "add FTS5 index",
        [
            """CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts 
           USING fts5(content, type, project, tags,
           content='memories', content_rowid='rowid')""",
        ],
    ),
]


def get_current_version(conn: Connection) -> int:
    """Get current schema version."""
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version "
            "(version INTEGER PRIMARY KEY, applied_at TEXT)"
        )
        row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        return row[0] or 0
    except Exception:
        return 0


def run_migrations(conn: Connection) -> None:
    """Run all pending migrations."""
    current = get_current_version(conn)
    pending = [m for m in MIGRATIONS if m[0] > current]

    if not pending:
        return

    for version, description, statements in pending:
        logger.info(f"Running migration v{version}: {description}")
        try:
            for sql in statements:
                try:
                    conn.execute(sql)
                except Exception as e:
                    # Column already exists etc - safe to ignore
                    logger.debug(f"Migration statement skipped: {e}")

            conn.execute(
                "INSERT INTO schema_version(version, applied_at) "
                "VALUES (?, datetime('now'))",
                (version,),
            )
            conn.commit()
            logger.info(f"Migration v{version} complete")
        except Exception as e:
            logger.error(f"Migration v{version} failed: {e}")
            raise
