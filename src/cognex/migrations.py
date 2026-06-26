"""SQLite schema migrations for Cognex.

Design principles
-----------------
1. **Forward-only, version-tracked.** Each migration has a monotonically
   increasing version number recorded in ``schema_version``.  Only
   pending migrations (version > current max) are executed.

2. **Savepoint-wrapped.** Every migration runs inside a SQLite SAVEPOINT
   so that a failure can be rolled back cleanly without leaving the
   database in a partially-migrated state.

3. **Checkpoint snapshots.** Before executing a migration, the current
   DDL of the affected tables is captured in ``migration_checkpoints``.
   A developer can inspect these records to reconstruct the pre-migration
   schema if a manual recovery is ever needed.

4. **Idempotent statements.** Every DDL statement uses ``IF NOT EXISTS``
   / ``IF EXISTS`` guards so that re-running the same migration (e.g.
   after a partial failure) does not raise errors.
"""

from __future__ import annotations

import json
import logging
from sqlite3 import Connection

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Migration list
#
# Each entry is a 3-tuple:
#   (version: int, description: str, statements: list[str])
#
# Statements are executed in order inside a single savepoint transaction.
# A statement that raises an OperationalError is silently skipped when the
# error looks like "duplicate column" or "already exists" — this handles
# the case where a migration was partially applied before a crash.
# ---------------------------------------------------------------------------

MIGRATIONS: list[tuple[int, str, list[str]]] = [
    # v1 — baseline (tables already created by _init_db)
    (1, "initial schema", []),

    # v2 — relevance decay support
    (2, "add relevance_score to memories", [
        "ALTER TABLE memories ADD COLUMN relevance_score REAL DEFAULT 1.0",
    ]),

    # v3 — memory priority tiers
    (3, "add tier to memories", [
        "ALTER TABLE memories ADD COLUMN tier INTEGER DEFAULT 2",
    ]),

    # v4 — access tracking
    (4, "add last_accessed to memories", [
        "ALTER TABLE memories ADD COLUMN last_accessed TEXT",
    ]),

    # v5 — FTS5 full-text search
    (5, "add FTS5 index", [
        """CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
           USING fts5(content, type, project, tags,
           content='memories', content_rowid='rowid')""",
    ]),

    # v6 — cognitive units and FTS
    (6, "add cognitive_units table", [
        """CREATE TABLE IF NOT EXISTS cognitive_units (
            unit_id TEXT PRIMARY KEY,
            unit_type TEXT NOT NULL DEFAULT 'decision',
            content TEXT NOT NULL,
            rationale TEXT DEFAULT '',
            scope TEXT DEFAULT '',
            confidence REAL DEFAULT 1.0,
            tags TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            session_id TEXT DEFAULT '',
            project TEXT DEFAULT '',
            override_count INTEGER DEFAULT 0,
            last_verified TEXT
        )""",
        "CREATE INDEX IF NOT EXISTS idx_cu_project ON cognitive_units(project)",
        "CREATE INDEX IF NOT EXISTS idx_cu_scope ON cognitive_units(scope)",
        "CREATE INDEX IF NOT EXISTS idx_cu_type ON cognitive_units(unit_type)",
        "CREATE INDEX IF NOT EXISTS idx_cu_confidence ON cognitive_units(confidence DESC)",
        """CREATE VIRTUAL TABLE IF NOT EXISTS cognitive_units_fts
           USING fts5(content, rationale,
           content='cognitive_units', content_rowid='rowid')""",
    ]),

    # v7 — change-log for cognitive units
    (7, "add cognitive_unit_deltas table", [
        """CREATE TABLE IF NOT EXISTS cognitive_unit_deltas (
            delta_id TEXT PRIMARY KEY,
            unit_id TEXT NOT NULL,
            changed_field TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            changed_by TEXT,
            changed_at TEXT NOT NULL,
            reason TEXT
        )""",
        "CREATE INDEX IF NOT EXISTS idx_cud_unit_id ON cognitive_unit_deltas(unit_id)",
        "CREATE INDEX IF NOT EXISTS idx_cud_changed_at ON cognitive_unit_deltas(changed_at)",
    ]),

    # v8 — content-hash deduplication
    (8, "add content_hash for deduplication", [
        "ALTER TABLE memories ADD COLUMN content_hash TEXT DEFAULT ''",
        "CREATE INDEX IF NOT EXISTS idx_mem_content_hash ON memories(content_hash)",
    ]),

    # v9 — append-only audit trail
    (9, "add audit_log table", [
        """CREATE TABLE IF NOT EXISTS audit_log (
            log_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            session_id TEXT,
            project TEXT,
            agent_id TEXT,
            payload TEXT,
            created_at TEXT NOT NULL,
            checksum TEXT NOT NULL
        )""",
        "CREATE INDEX IF NOT EXISTS idx_audit_log_project ON audit_log(project)",
        "CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at DESC)",
    ]),

    # v10 — audit log hash chain
    #
    # Each entry now includes the checksum of the previous entry so that
    # deletions anywhere in the log invalidate all subsequent checksums.
    # Existing rows get the sentinel value 'GENESIS' as their prev_checksum,
    # which verify_chain() treats as the valid chain root.
    (10, "add prev_checksum to audit_log for hash-chain tamper detection", [
        "ALTER TABLE audit_log ADD COLUMN prev_checksum TEXT DEFAULT 'GENESIS'",
    ]),

    # v11 — normalised tag storage
    #
    # Tags were previously stored as a JSON array string in memories.tags.
    # This junction table enables index-backed tag queries.  The JSON
    # column is kept for serialisation compatibility (teleport bundles).
    (11, "add memory_tags junction table", [
        """CREATE TABLE IF NOT EXISTS memory_tags (
            memory_id TEXT NOT NULL,
            tag       TEXT NOT NULL,
            PRIMARY KEY (memory_id, tag),
            FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
        )""",
        "CREATE INDEX IF NOT EXISTS idx_memory_tags_tag       ON memory_tags(tag)",
        "CREATE INDEX IF NOT EXISTS idx_memory_tags_memory_id ON memory_tags(memory_id)",
        # Backfill: populate junction table from existing JSON tag columns.
        """INSERT OR IGNORE INTO memory_tags (memory_id, tag)
           SELECT m.id, je.value
           FROM   memories m,
                  json_each(m.tags) AS je
           WHERE  m.tags IS NOT NULL
             AND  m.tags != '[]'""",
    ]),

    # v12 — vector embeddings for semantic retrieval
    #
    # Embeddings are stored as raw IEEE-754 binary blobs (struct-packed
    # float32 arrays) to keep the dependency surface minimal.  Cosine
    # similarity is computed in Python rather than via a sqlite-vec
    # extension, making the feature available without native extensions.
    (12, "add memory_embeddings table for semantic search", [
        """CREATE TABLE IF NOT EXISTS memory_embeddings (
            memory_id  TEXT PRIMARY KEY,
            embedding  BLOB NOT NULL,
            model_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
        )""",
    ]),

    # v13 — session-scoped memory access log for outcome feedback
    #
    # Tracks which memories were retrieved during each session so that
    # outcome_feedback can retroactively adjust their relevance_score
    # when ledger_outcome() is called.
    (13, "add memory_access_log for outcome-conditioned weighting", [
        """CREATE TABLE IF NOT EXISTS memory_access_log (
            id         TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            memory_id  TEXT NOT NULL,
            accessed_at TEXT NOT NULL
        )""",
        "CREATE INDEX IF NOT EXISTS idx_access_log_session  ON memory_access_log(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_access_log_memory   ON memory_access_log(memory_id)",
    ]),

    # v14 — three-tier memory hierarchy
    #
    # Tier 1: episodic memories (existing `memories` table)
    # Tier 2: semantic clusters — synthesised generalisations from groups
    #         of episodic memories that share a common theme
    # Tier 3: procedural schemas — durable behavioural patterns that do
    #         not decay and are only explicitly overridden
    (14, "add memory_clusters and memory_schemas for hierarchical memory", [
        """CREATE TABLE IF NOT EXISTS memory_clusters (
            cluster_id        TEXT PRIMARY KEY,
            project           TEXT DEFAULT '',
            theme             TEXT NOT NULL,
            summary           TEXT NOT NULL,
            source_memory_ids TEXT DEFAULT '[]',
            created_at        TEXT NOT NULL,
            last_updated      TEXT NOT NULL,
            confidence        REAL DEFAULT 1.0
        )""",
        "CREATE INDEX IF NOT EXISTS idx_clusters_project ON memory_clusters(project)",
        """CREATE TABLE IF NOT EXISTS memory_schemas (
            schema_id          TEXT PRIMARY KEY,
            project            TEXT DEFAULT '',
            name               TEXT NOT NULL,
            description        TEXT NOT NULL,
            source_cluster_ids TEXT DEFAULT '[]',
            created_at         TEXT NOT NULL,
            last_verified      TEXT
        )""",
        "CREATE INDEX IF NOT EXISTS idx_schemas_project ON memory_schemas(project)",
    ]),

    # v15 — session arc abstraction for temporal context windows
    #
    # Groups related sessions (same project, gap ≤ 7 days) into arcs
    # so an agent can retrieve a higher-level narrative of recent work
    # rather than replaying raw session summaries.
    (15, "add session_arcs for temporal context windows", [
        """CREATE TABLE IF NOT EXISTS session_arcs (
            arc_id            TEXT PRIMARY KEY,
            project           TEXT NOT NULL,
            arc_summary       TEXT DEFAULT '',
            session_ids       TEXT DEFAULT '[]',
            started_at        TEXT NOT NULL,
            last_session_at   TEXT NOT NULL,
            cumulative_decisions TEXT DEFAULT '[]',
            known_blockers    TEXT DEFAULT '[]',
            status            TEXT DEFAULT 'active'
        )""",
        "CREATE INDEX IF NOT EXISTS idx_arcs_project      ON session_arcs(project)",
        "CREATE INDEX IF NOT EXISTS idx_arcs_last_session ON session_arcs(last_session_at DESC)",
    ]),
]


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------

def _ensure_checkpoint_table(conn: Connection) -> None:
    """Create migration_checkpoints table if it does not yet exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS migration_checkpoints (
            version          INTEGER PRIMARY KEY,
            checkpoint_at    TEXT NOT NULL,
            schema_snapshot  TEXT NOT NULL
        )
    """)


def _capture_checkpoint(conn: Connection, version: int) -> None:
    """Snapshot DDL of every table before running *version*.

    The snapshot is a JSON object mapping table name → CREATE TABLE DDL.
    It is stored in ``migration_checkpoints`` so a developer can inspect
    it later and manually reconstruct the schema if needed.
    """
    rows = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type = 'table' AND sql IS NOT NULL"
    ).fetchall()
    snapshot = {row["name"]: row["sql"] for row in rows}
    conn.execute(
        "INSERT OR REPLACE INTO migration_checkpoints (version, checkpoint_at, schema_snapshot) "
        "VALUES (?, datetime('now'), ?)",
        (version, json.dumps(snapshot)),
    )


# ---------------------------------------------------------------------------
# Version management
# ---------------------------------------------------------------------------

def get_current_version(conn: Connection) -> int:
    """Return the highest applied migration version (0 if none)."""
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version "
            "(version INTEGER PRIMARY KEY, applied_at TEXT)"
        )
        row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        return row[0] or 0
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_migrations(conn: Connection) -> None:
    """Apply all pending migrations in ascending version order.

    Each migration is wrapped in a SQLite SAVEPOINT so that a failure
    rolls back only that migration, leaving the database in the last
    successfully migrated state.  This replaces the previous behaviour
    where a mid-migration failure could leave the schema partially
    updated with no clean recovery path.
    """
    _ensure_checkpoint_table(conn)

    current = get_current_version(conn)
    pending = [m for m in MIGRATIONS if m[0] > current]

    if not pending:
        return

    for version, description, statements in pending:
        savepoint = f"migration_v{version}"
        logger.info("Running migration v%s: %s", version, description)

        try:
            # Capture DDL snapshot before making any changes.
            _capture_checkpoint(conn, version)

            conn.execute(f"SAVEPOINT {savepoint}")

            for sql in statements:
                try:
                    conn.execute(sql)
                except Exception as exc:
                    msg = str(exc).lower()
                    # Tolerate idempotent failures (column/table already exists).
                    if "already exists" in msg or "duplicate column" in msg:
                        logger.debug("Migration v%s skipped statement (already applied): %s", version, exc)
                    else:
                        raise

            # Record the applied version.
            conn.execute(
                "INSERT INTO schema_version(version, applied_at) VALUES (?, datetime('now'))",
                (version,),
            )
            conn.execute(f"RELEASE SAVEPOINT {savepoint}")
            conn.commit()
            logger.info("Migration v%s complete", version)

        except Exception as exc:
            logger.error("Migration v%s failed: %s — rolling back", version, exc)
            try:
                conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                conn.execute(f"RELEASE SAVEPOINT {savepoint}")
            except Exception:
                pass
            raise
