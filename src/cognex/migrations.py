
from __future__ import annotations

import json
import logging
from sqlite3 import Connection

logger = logging.getLogger(__name__)

# Each migration is a (version, description, statements) tuple.
# Statements run in a savepoint; "already exists" errors are tolerated.

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

    # v16 — large memory support
    #
    # Long memories are split into overlapping chunks for FTS5 retrieval;
    # search matches at chunk level but returns the parent memory.  A
    # one-line gist column powers compact search listings.
    (16, "add memory_chunks, memory_chunks_fts, and gist column", [
        "ALTER TABLE memories ADD COLUMN gist TEXT DEFAULT ''",
        """CREATE TABLE IF NOT EXISTS memory_chunks (
            chunk_id    TEXT PRIMARY KEY,
            memory_id   TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            text        TEXT NOT NULL,
            FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
        )""",
        "CREATE INDEX IF NOT EXISTS idx_chunks_memory_id ON memory_chunks(memory_id)",
        """CREATE VIRTUAL TABLE IF NOT EXISTS memory_chunks_fts
           USING fts5(text, content='memory_chunks', content_rowid='rowid')""",
        """CREATE TRIGGER IF NOT EXISTS chunks_fts_insert
           AFTER INSERT ON memory_chunks BEGIN
               INSERT INTO memory_chunks_fts(rowid, text)
               VALUES (new.rowid, new.text);
           END""",
        """CREATE TRIGGER IF NOT EXISTS chunks_fts_delete
           AFTER DELETE ON memory_chunks BEGIN
               DELETE FROM memory_chunks_fts WHERE rowid = old.rowid;
           END""",
        """CREATE TRIGGER IF NOT EXISTS chunks_fts_update
           AFTER UPDATE ON memory_chunks BEGIN
               DELETE FROM memory_chunks_fts WHERE rowid = old.rowid;
               INSERT INTO memory_chunks_fts(rowid, text)
               VALUES (new.rowid, new.text);
           END""",
        # Backfill gist for existing rows (first <=120 chars of content).
        "UPDATE memories SET gist = substr(content, 1, 120) WHERE gist = '' AND content != ''",
    ]),

    # v17 — provenance graph substrate
    (17, "add provenance graph tables", [
        """CREATE TABLE IF NOT EXISTS provenance_nodes (
            node_id    TEXT PRIMARY KEY,
            node_type  TEXT NOT NULL,
            ref_table  TEXT NOT NULL,
            ref_id     TEXT NOT NULL,
            project    TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            session_id TEXT DEFAULT ''
        )""",
        """CREATE TABLE IF NOT EXISTS provenance_edges (
            edge_id    TEXT PRIMARY KEY,
            from_node  TEXT NOT NULL,
            to_node    TEXT NOT NULL,
            edge_type  TEXT NOT NULL,
            rationale  TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (from_node) REFERENCES provenance_nodes(node_id),
            FOREIGN KEY (to_node) REFERENCES provenance_nodes(node_id)
        )""",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_prov_nodes_ref ON provenance_nodes(ref_table, ref_id, node_type)",
        "CREATE INDEX IF NOT EXISTS idx_prov_nodes_project_type ON provenance_nodes(project, node_type)",
        "CREATE INDEX IF NOT EXISTS idx_prov_edges_from ON provenance_edges(from_node)",
        "CREATE INDEX IF NOT EXISTS idx_prov_edges_to ON provenance_edges(to_node)",
    ]),

    # v18 — explicit epistemic state and known unknowns
    (18, "add epistemic state columns and open questions", [
        "ALTER TABLE cognitive_units ADD COLUMN epistemic_status TEXT DEFAULT 'assumed'",
        "ALTER TABLE cognitive_units ADD COLUMN verification_condition TEXT DEFAULT ''",
        "ALTER TABLE cognitive_units ADD COLUMN depends_on TEXT DEFAULT '[]'",
        "ALTER TABLE cognitive_units ADD COLUMN staleness_deadline TEXT",
        """CREATE TABLE IF NOT EXISTS open_questions (
            question_id       TEXT PRIMARY KEY,
            content           TEXT NOT NULL,
            project           TEXT DEFAULT '',
            scope             TEXT DEFAULT '',
            raised_in_session TEXT DEFAULT '',
            status            TEXT DEFAULT 'open',
            answer_ref        TEXT,
            created_at        TEXT NOT NULL
        )""",
        "CREATE INDEX IF NOT EXISTS idx_open_questions_project_status ON open_questions(project, status)",
    ]),

    # v19 — Merkle integrity snapshots
    (19, "add integrity root snapshots", [
        """CREATE TABLE IF NOT EXISTS integrity_roots (
            root_hash    TEXT PRIMARY KEY,
            project      TEXT NOT NULL,
            computed_at  TEXT NOT NULL,
            record_count INTEGER NOT NULL,
            signature    TEXT DEFAULT '',
            key_fingerprint TEXT DEFAULT ''
        )""",
        "CREATE INDEX IF NOT EXISTS idx_integrity_roots_project_time ON integrity_roots(project, computed_at DESC)",
    ]),

    # v20 — reconciliation conflict journal
    (20, "add reconciliation conflicts", [
        """CREATE TABLE IF NOT EXISTS reconciliation_conflicts (
            conflict_id   TEXT PRIMARY KEY,
            item_class    TEXT NOT NULL,
            local_ref     TEXT DEFAULT '',
            incoming_ref  TEXT DEFAULT '',
            project       TEXT DEFAULT '',
            scope         TEXT DEFAULT '',
            local_line    TEXT DEFAULT '',
            incoming_line TEXT DEFAULT '',
            resolution    TEXT DEFAULT '',
            rationale     TEXT DEFAULT '',
            created_at    TEXT NOT NULL,
            resolved_at   TEXT
        )""",
        "CREATE INDEX IF NOT EXISTS idx_reconcile_project ON reconciliation_conflicts(project, resolution)",
    ]),
]


# Checkpoint helpers

def _ensure_checkpoint_table(conn: Connection) -> None:

    conn.execute("""
        CREATE TABLE IF NOT EXISTS migration_checkpoints (
            version          INTEGER PRIMARY KEY,
            checkpoint_at    TEXT NOT NULL,
            schema_snapshot  TEXT NOT NULL
        )
    """)


def _capture_checkpoint(conn: Connection, version: int) -> None:
    rows = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type = 'table' AND sql IS NOT NULL"
    ).fetchall()
    snapshot = {row["name"]: row["sql"] for row in rows}
    conn.execute(
        "INSERT OR REPLACE INTO migration_checkpoints (version, checkpoint_at, schema_snapshot) "
        "VALUES (?, datetime('now'), ?)",
        (version, json.dumps(snapshot)),
    )


# Version management

def get_current_version(conn: Connection) -> int:
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version "
            "(version INTEGER PRIMARY KEY, applied_at TEXT)"
        )
        row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        return row[0] or 0
    except Exception:
        return 0


# Main entry point

def run_migrations(conn: Connection) -> None:
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
