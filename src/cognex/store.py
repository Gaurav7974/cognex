
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
import struct
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ._pool import ConnectionPool, execute_with_retry
from .embeddings import EmbeddingEngine
from .migrations import run_migrations
from .models import MemoryEntry, MemoryScope, MemoryType, SessionSnapshot

logger = logging.getLogger(__name__)

_DECAY_PAGE_SIZE = 1_000


class MemoryStore:

    def __init__(
        self,
        db_path: str | Path | None = None,
        pool_size: int | None = None,
    ) -> None:
        self.db_path = Path(db_path) if db_path else Path.home() / ".cognex.db" / "cognex.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        if pool_size is None:
            pool_size = int(os.getenv("COGNEX_POOL_SIZE", "3"))

        self._pool = ConnectionPool(self.db_path, pool_size=pool_size)
        self._init_db()


    def _connect(self):
        return self._pool.get_connection()

    def close(self) -> None:
        self._pool.close_all()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS memories (
                    id              TEXT PRIMARY KEY,
                    type            TEXT NOT NULL,
                    scope           TEXT NOT NULL DEFAULT 'private',
                    content         TEXT NOT NULL,
                    context         TEXT DEFAULT '',
                    relevance_score REAL DEFAULT 1.0,
                    created_at      TEXT NOT NULL,
                    last_accessed   TEXT,
                    access_count    INTEGER DEFAULT 0,
                    project         TEXT DEFAULT '',
                    tags            TEXT DEFAULT '[]',
                    content_hash    TEXT DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_mem_type      ON memories(type);
                CREATE INDEX IF NOT EXISTS idx_mem_project   ON memories(project);
                CREATE INDEX IF NOT EXISTS idx_mem_relevance ON memories(relevance_score DESC);
                CREATE INDEX IF NOT EXISTS idx_mem_created   ON memories(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_mem_hash      ON memories(content_hash);

                CREATE TABLE IF NOT EXISTS sessions (
                    session_id         TEXT PRIMARY KEY,
                    project            TEXT DEFAULT '',
                    summary            TEXT DEFAULT '',
                    key_decisions      TEXT DEFAULT '[]',
                    tools_used         TEXT DEFAULT '[]',
                    errors_encountered TEXT DEFAULT '[]',
                    started_at         TEXT NOT NULL,
                    ended_at           TEXT,
                    input_tokens       INTEGER DEFAULT 0,
                    output_tokens      INTEGER DEFAULT 0,
                    memory_ids         TEXT DEFAULT '[]'
                );

                CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project);
                CREATE INDEX IF NOT EXISTS idx_sessions_started  ON sessions(started_at DESC);
            """)


            try:
                conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
                    USING fts5(
                        content, context, type, project, tags,
                        content='memories',
                        content_rowid='rowid'
                    )
                """)


                fts_count = conn.execute(
                    "SELECT COUNT(*) FROM memories_fts"
                ).fetchone()[0]
                if fts_count == 0:
                    conn.execute("""
                        INSERT OR IGNORE INTO memories_fts
                            (rowid, content, context, type, project, tags)
                        SELECT rowid, content, context, type, project, tags
                        FROM   memories
                    """)


                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS memories_fts_insert
                    AFTER INSERT ON memories BEGIN
                        INSERT INTO memories_fts(rowid, content, context, type, project, tags)
                        VALUES (new.rowid, new.content, new.context, new.type,
                                new.project, new.tags);
                    END
                """)
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS memories_fts_update
                    AFTER UPDATE ON memories BEGIN
                        UPDATE memories_fts
                        SET    content=new.content, context=new.context,
                               type=new.type, project=new.project, tags=new.tags
                        WHERE  rowid=old.rowid;
                    END
                """)
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS memories_fts_delete
                    AFTER DELETE ON memories BEGIN
                        DELETE FROM memories_fts WHERE rowid=old.rowid;
                    END
                """)
            except Exception:
                pass

            run_migrations(conn)
            conn.commit()


    def _save_tags(self, conn: sqlite3.Connection, memory_id: str, tags: tuple) -> None:
        if not tags:
            return
        try:
            conn.executemany(
                "INSERT OR IGNORE INTO memory_tags (memory_id, tag) VALUES (?, ?)",
                [(memory_id, t) for t in tags],
            )
        except sqlite3.OperationalError:
            pass

    def _delete_tags(self, conn: sqlite3.Connection, memory_id: str) -> None:
        try:
            conn.execute(
                "DELETE FROM memory_tags WHERE memory_id = ?", (memory_id,)
            )
        except sqlite3.OperationalError:
            pass

    def _save_embedding(self, conn: sqlite3.Connection, memory_id: str, content: str) -> None:
        if not EmbeddingEngine.AVAILABLE:
            return
        try:
            vec = EmbeddingEngine.embed(content)
            blob = struct.pack(f"{len(vec)}f", *vec)
            conn.execute(
                """
                INSERT OR REPLACE INTO memory_embeddings
                (memory_id, embedding, model_name, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    memory_id,
                    blob,
                    EmbeddingEngine.MODEL_NAME,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        except Exception as e:
            logger.error("Failed to save embedding for memory %s: %s", memory_id, e)

    def _save_embeddings_bulk(self, conn: sqlite3.Connection, to_insert: list[tuple]) -> None:
        if not to_insert or not EmbeddingEngine.AVAILABLE:
            return
        try:
            contents = [item[3] for item in to_insert]
            vecs = EmbeddingEngine.embed_batch(contents)
            embedding_rows = []
            now_str = datetime.now(timezone.utc).isoformat()
            for item, vec in zip(to_insert, vecs):
                memory_id = item[0]
                blob = struct.pack(f"{len(vec)}f", *vec)
                embedding_rows.append((memory_id, blob, EmbeddingEngine.MODEL_NAME, now_str))
            if embedding_rows:
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO memory_embeddings
                    (memory_id, embedding, model_name, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    embedding_rows,
                )
        except Exception as e:
            logger.error("Failed to save embeddings in bulk: %s", e)

    # ------------------------------------------------------------------
    # Large-memory support: gists + chunking
    # ------------------------------------------------------------------

    _CHUNK_THRESHOLD = 1500
    _CHUNK_MIN_WORDS = 200
    _CHUNK_MAX_WORDS = 400
    _CHUNK_OVERLAP = 0.15
    _GIST_MAX = 120

    @staticmethod
    def _make_gist(content: str) -> str:
        if not content:
            return ""
        first_sentence = re.split(r"(?<=[.!?])\s+|\n", content.strip(), maxsplit=1)[0]
        gist = first_sentence if first_sentence else content.strip()
        if len(gist) > MemoryStore._GIST_MAX:
            return gist[: MemoryStore._GIST_MAX - 1] + "\u2026"
        return gist

    @staticmethod
    def _chunk_content(content: str) -> list[tuple[int, str]]:
        if len(content) <= MemoryStore._CHUNK_THRESHOLD:
            return []
        import re as _re
        sentences = [s for s in _re.split(r"(?<=[.!?])\s+|\n+", content) if s.strip()]
        if not sentences:
            return []
        chunks: list[tuple[int, str]] = []
        idx = 0
        i = 0
        n = len(sentences)
        while i < n:
            words: list[str] = []
            j = i
            while j < n:
                sent_words = sentences[j].split()
                if len(words) + len(sent_words) > MemoryStore._CHUNK_MAX_WORDS and words:
                    break
                words.extend(sent_words)
                j += 1
                if len(words) >= MemoryStore._CHUNK_MIN_WORDS:
                    break
            chunk_text = " ".join(words)
            chunks.append((idx, chunk_text))
            idx += 1
            overlap = max(1, int(len(words) * MemoryStore._CHUNK_OVERLAP))
            carry = words[-overlap:]
            i = j
            if i < n:
                next_words: list[str] = list(carry)
                while i < n and len(next_words) < MemoryStore._CHUNK_MIN_WORDS:
                    sent_words = sentences[i].split()
                    next_words.extend(sent_words)
                    i += 1
                if len(next_words) >= MemoryStore._CHUNK_MIN_WORDS:
                    chunks.append((idx, " ".join(next_words)))
                    idx += 1
        return chunks

    def _save_chunks(self, conn: sqlite3.Connection, memory_id: str, content: str) -> None:
        try:
            conn.execute("DELETE FROM memory_chunks WHERE memory_id = ?", (memory_id,))
        except sqlite3.OperationalError:
            return
        chunks = self._chunk_content(content)
        if not chunks:
            return
        rows = [(uuid.uuid4().hex[:12], memory_id, ci, text) for ci, text in chunks]
        try:
            conn.executemany(
                "INSERT INTO memory_chunks (chunk_id, memory_id, chunk_index, text) "
                "VALUES (?, ?, ?, ?)",
                rows,
            )
        except sqlite3.OperationalError:
            pass

    def _delete_chunks(self, conn: sqlite3.Connection, memory_id: str) -> None:
        try:
            conn.execute("DELETE FROM memory_chunks WHERE memory_id = ?", (memory_id,))
        except sqlite3.OperationalError:
            pass

    def _chunks_fts5_available(self, conn: sqlite3.Connection) -> bool:
        try:
            conn.execute("SELECT 1 FROM memory_chunks_fts LIMIT 1")
            return True
        except sqlite3.OperationalError:
            return False

    def save(self, memory: MemoryEntry, session_id: str = "") -> MemoryEntry:
        content_hash = hashlib.sha256(memory.content.encode()).hexdigest()[:16]

        with self._connect() as conn:
            existing = execute_with_retry(
                conn,
                "SELECT id FROM memories WHERE content_hash = ? AND project = ? LIMIT 1",
                (content_hash, memory.project),
            ).fetchone()

            if existing:
                row = conn.execute(
                    "SELECT * FROM memories WHERE id = ?", (existing[0],)
                ).fetchone()
                return self._row_to_memory(row)

            execute_with_retry(
                conn,
                """
                INSERT INTO memories
                (id, type, scope, content, context, relevance_score,
                 created_at, last_accessed, access_count, project, tags,
                 content_hash, gist)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory.id,
                    memory.type.value,
                    memory.scope.value,
                    memory.content,
                    memory.context,
                    memory.relevance_score,
                    memory.created_at.isoformat(),
                    memory.last_accessed.isoformat() if memory.last_accessed else None,
                    memory.access_count,
                    memory.project,
                    json.dumps(list(memory.tags)),
                    content_hash,
                    self._make_gist(memory.content),
                ),
            )
            self._save_tags(conn, memory.id, memory.tags)
            self._save_chunks(conn, memory.id, memory.content)
            self._save_embedding(conn, memory.id, memory.content)
            if session_id:
                self._log_access(conn, session_id, memory.id)
            conn.commit()

        return memory

    def save_many(self, memories: list[MemoryEntry], session_id: str = "") -> int:
        if not memories:
            return 0

        with self._connect() as conn:
            # Load existing hashes for the relevant projects in one query.
            projects = list({m.project for m in memories})
            placeholders = ",".join("?" * len(projects))
            existing_hashes: set[str] = set()
            if projects:
                rows = conn.execute(
                    f"SELECT content_hash FROM memories WHERE project IN ({placeholders})",
                    projects,
                ).fetchall()
                existing_hashes = {r[0] for r in rows}

            to_insert: list[tuple] = []
            tag_rows: list[tuple[str, str]] = []

            for m in memories:
                content_hash = hashlib.sha256(m.content.encode()).hexdigest()[:16]
                if content_hash in existing_hashes:
                    continue
                existing_hashes.add(content_hash)
                to_insert.append((
                    m.id,
                    m.type.value,
                    m.scope.value,
                    m.content,
                    m.context,
                    m.relevance_score,
                    m.created_at.isoformat(),
                    m.last_accessed.isoformat() if m.last_accessed else None,
                    m.access_count,
                    m.project,
                    json.dumps(list(m.tags)),
                    content_hash,
                    self._make_gist(m.content),
                ))
                for tag in m.tags:
                    tag_rows.append((m.id, tag))

            if to_insert:
                conn.executemany(
                    """
                    INSERT INTO memories
                    (id, type, scope, content, context, relevance_score,
                     created_at, last_accessed, access_count, project, tags,
                     content_hash, gist)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    to_insert,
                )
                if tag_rows:
                    try:
                        conn.executemany(
                            "INSERT OR IGNORE INTO memory_tags (memory_id, tag) VALUES (?, ?)",
                            tag_rows,
                        )
                    except sqlite3.OperationalError:
                        pass  # memory_tags not yet migrated
                for item in to_insert:
                    self._save_chunks(conn, item[0], item[3])
                self._save_embeddings_bulk(conn, to_insert)
                conn.commit()

        return len(to_insert)

    def save_many_bulk(self, memories: list[MemoryEntry]) -> int:
        if not memories:
            return 0

        with self._connect() as conn:
            fts_available = self._fts5_available(conn)

            if not fts_available:
                return self.save_many(memories)


            conn.execute("DROP TRIGGER IF EXISTS memories_fts_insert")
            conn.execute("DROP TRIGGER IF EXISTS memories_fts_update")
            conn.execute("DROP TRIGGER IF EXISTS memories_fts_delete")
            chunks_fts = self._chunks_fts5_available(conn)
            if chunks_fts:
                conn.execute("DROP TRIGGER IF EXISTS chunks_fts_insert")
                conn.execute("DROP TRIGGER IF EXISTS chunks_fts_update")
                conn.execute("DROP TRIGGER IF EXISTS chunks_fts_delete")


            projects = list({m.project for m in memories})
            placeholders = ",".join("?" * len(projects))
            existing_hashes: set[str] = set()
            if projects:
                rows = conn.execute(
                    f"SELECT content_hash FROM memories WHERE project IN ({placeholders})",
                    projects,
                ).fetchall()
                existing_hashes = {r[0] for r in rows}

            to_insert: list[tuple] = []
            tag_rows: list[tuple[str, str]] = []
            for m in memories:
                content_hash = hashlib.sha256(m.content.encode()).hexdigest()[:16]
                if content_hash in existing_hashes:
                    continue
                existing_hashes.add(content_hash)
                to_insert.append((
                    m.id,
                    m.type.value,
                    m.scope.value,
                    m.content,
                    m.context,
                    m.relevance_score,
                    m.created_at.isoformat(),
                    m.last_accessed.isoformat() if m.last_accessed else None,
                    m.access_count,
                    m.project,
                    json.dumps(list(m.tags)),
                    content_hash,
                    self._make_gist(m.content),
                ))
                for tag in m.tags:
                    tag_rows.append((m.id, tag))

            if to_insert:
                conn.executemany(
                    """
                    INSERT INTO memories
                    (id, type, scope, content, context, relevance_score,
                     created_at, last_accessed, access_count, project, tags,
                     content_hash, gist)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    to_insert,
                )
                if tag_rows:
                    try:
                        conn.executemany(
                            "INSERT OR IGNORE INTO memory_tags (memory_id, tag) VALUES (?, ?)",
                            tag_rows,
                        )
                    except sqlite3.OperationalError:
                        pass
                for item in to_insert:
                    self._save_chunks(conn, item[0], item[3])

                self._save_embeddings_bulk(conn, to_insert)


                try:
                    conn.execute(
                        "INSERT INTO memories_fts(memories_fts) VALUES('rebuild')"
                    )
                except Exception:
                    pass
                if chunks_fts:
                    try:
                        conn.execute(
                            "INSERT INTO memory_chunks_fts(memory_chunks_fts) VALUES('rebuild')"
                        )
                    except Exception:
                        pass

                conn.commit()


            try:
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS memories_fts_insert
                    AFTER INSERT ON memories BEGIN
                        INSERT INTO memories_fts(rowid, content, context, type, project, tags)
                        VALUES (new.rowid, new.content, new.context, new.type,
                                new.project, new.tags);
                    END
                """)
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS memories_fts_update
                    AFTER UPDATE ON memories BEGIN
                        UPDATE memories_fts
                        SET    content=new.content, context=new.context,
                               type=new.type, project=new.project, tags=new.tags
                        WHERE  rowid=old.rowid;
                    END
                """)
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS memories_fts_delete
                    AFTER DELETE ON memories BEGIN
                        DELETE FROM memories_fts WHERE rowid=old.rowid;
                    END
                """)
            except Exception:
                pass
            if chunks_fts:
                try:
                    conn.execute("""
                        CREATE TRIGGER IF NOT EXISTS chunks_fts_insert
                        AFTER INSERT ON memory_chunks BEGIN
                            INSERT INTO memory_chunks_fts(rowid, text)
                            VALUES (new.rowid, new.text);
                        END
                    """)
                    conn.execute("""
                        CREATE TRIGGER IF NOT EXISTS chunks_fts_delete
                        AFTER DELETE ON memory_chunks BEGIN
                            DELETE FROM memory_chunks_fts WHERE rowid = old.rowid;
                        END
                    """)
                    conn.execute("""
                        CREATE TRIGGER IF NOT EXISTS chunks_fts_update
                        AFTER UPDATE ON memory_chunks BEGIN
                            DELETE FROM memory_chunks_fts WHERE rowid = old.rowid;
                            INSERT INTO memory_chunks_fts(rowid, text)
                            VALUES (new.rowid, new.text);
                        END
                    """)
                except Exception:
                    pass

        return len(to_insert)

    def get(self, memory_id: str, session_id: str = "") -> MemoryEntry | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM memories WHERE id = ?", (memory_id,)
            ).fetchone()
        if not row:
            return None

        entry = self._row_to_memory(row)
        touched = entry.touch()
        # Persist the touch (relevance boost + access_count++) without
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE memories
                SET    relevance_score = ?,
                       access_count    = ?,
                       last_accessed   = ?
                WHERE  id = ?
                """,
                (
                    touched.relevance_score,
                    touched.access_count,
                    touched.last_accessed.isoformat() if touched.last_accessed else None,
                    memory_id,
                ),
            )

            if session_id:
                self._log_access(conn, session_id, memory_id)
            conn.commit()

        return touched

    def _log_access(
        self, conn: sqlite3.Connection, session_id: str, memory_id: str
    ) -> None:
        try:
            conn.execute(
                """
                INSERT INTO memory_access_log (id, session_id, memory_id, accessed_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex[:12],
                    session_id,
                    memory_id,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        except sqlite3.OperationalError:
            pass  # Table not yet created (pre-v13 database).

    def delete(self, memory_id: str) -> bool:
        with self._connect() as conn:
            self._delete_tags(conn, memory_id)
            cur = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            conn.commit()
        return cur.rowcount > 0

    def count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]


    def boost_relevance(self, memory_id: str, delta: float = 0.05) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE memories
                SET    relevance_score = MIN(2.0, relevance_score + ?)
                WHERE  id = ?
                """,
                (delta, memory_id),
            )
            conn.commit()

    def penalize_relevance(self, memory_id: str, delta: float = 0.03) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE memories
                SET    relevance_score = MAX(0.01, relevance_score - ?)
                WHERE  id = ?
                """,
                (delta, memory_id),
            )
            conn.commit()


    def _fts5_available(self, conn: sqlite3.Connection) -> bool:
        try:
            conn.execute("SELECT 1 FROM memories_fts LIMIT 1")
            return True
        except sqlite3.OperationalError:
            return False

    def _tags_table_available(self, conn: sqlite3.Connection) -> bool:
        try:
            conn.execute("SELECT 1 FROM memory_tags LIMIT 1")
            return True
        except sqlite3.OperationalError:
            return False

    def search(
        self,
        query: str = "",
        memory_type: MemoryType | None = None,
        project: str = "",
        scope: MemoryScope | None = None,
        tags: tuple[str, ...] = (),
        limit: int = 20,
        min_relevance: float = 0.0,
        boost_project: str = "",
        recency_days: int = 0,
    ) -> list[MemoryEntry]:
        with self._connect() as conn:
            if query and self._fts5_available(conn):
                if self._chunks_fts5_available(conn):
                    try:
                        return self._search_chunks_fts5(
                            conn, query, memory_type, project, scope, tags,
                            limit, min_relevance, boost_project, recency_days,
                        )
                    except sqlite3.OperationalError:
                        pass
                return self._search_fts5(
                    conn, query, memory_type, project, scope, tags,
                    limit, min_relevance, boost_project, recency_days,
                )
            return self._search_like(
                conn, query, memory_type, project, scope, tags,
                limit, min_relevance, boost_project, recency_days,
            )

    def get_search_type(self, query: str = "") -> str:
        if not query:
            return "like_fallback"
        with self._connect() as conn:
            if not self._fts5_available(conn):
                return "like_fallback"
            return "fts5_chunks" if self._chunks_fts5_available(conn) else "fts5_bm25"

    def _build_tag_condition(
        self,
        conn: sqlite3.Connection,
        tags: tuple[str, ...],
        params: list,
    ) -> str:
        if not tags:
            return ""

        if self._tags_table_available(conn):
            conditions = []
            for tag in tags:
                conditions.append(
                    "EXISTS (SELECT 1 FROM memory_tags mt "
                    "WHERE mt.memory_id = m.id AND mt.tag = ?)"
                )
                params.append(tag)
            return " AND ".join(conditions)
        else:
            conditions = []
            for tag in tags:
                conditions.append("m.tags LIKE ? COLLATE NOCASE")
                params.append(f'%"{tag}"%')
            return " AND ".join(conditions)

    def _escape_fts5_query(self, query: str) -> str:
        for char in ['"', "'", "(", ")", "*", "-", "+", ":", "^", "{", "}", "[", "]"]:
            query = query.replace(char, " ")
        words = query.split()
        if not words:
            return '""'
        return " OR ".join(f"{w}*" for w in words if w)

    def _search_chunks_fts5(
        self,
        conn: sqlite3.Connection,
        query: str,
        memory_type: MemoryType | None,
        project: str,
        scope: MemoryScope | None,
        tags: tuple[str, ...],
        limit: int,
        min_relevance: float,
        boost_project: str,
        recency_days: int,
    ) -> list[MemoryEntry]:
        conditions: list[str] = []
        params: list = []

        if memory_type:
            conditions.append("m.type = ?")
            params.append(memory_type.value)
        if project:
            conditions.append("m.project = ?")
            params.append(project)
        if scope:
            conditions.append("m.scope = ?")
            params.append(scope.value)
        if min_relevance > 0:
            conditions.append("m.relevance_score >= ?")
            params.append(min_relevance)
        if tags:
            tag_cond = self._build_tag_condition(conn, tags, params)
            if tag_cond:
                conditions.append(tag_cond)

        where = " AND ".join(conditions) if conditions else "1=1"

        project_boost = ""
        project_boost_params: list = []
        if boost_project:
            project_boost = (
                "CASE WHEN m.project = ? THEN 1 ELSE 0 END AS proj_match,"
            )
            project_boost_params = [boost_project]

        recency_boost = ""
        recency_boost_params: list = []
        if recency_days > 0:
            recency_boost = (
                "CASE WHEN julianday('now') - julianday(m.created_at) <= ? "
                "THEN 1 ELSE 0 END AS is_recent,"
            )
            recency_boost_params = [recency_days]

        order_by_extra = ""
        if boost_project and recency_days > 0:
            order_by_extra = "proj_match DESC, is_recent DESC,"
        elif boost_project:
            order_by_extra = "proj_match DESC,"
        elif recency_days > 0:
            order_by_extra = "is_recent DESC,"

        fts_query = self._escape_fts5_query(query)

        # Unified search: hit the full-content index AND the chunk index,
        # dedup by parent memory id keeping the best score.  Short (un-
        # chunked) memories live only in memories_fts; long memories live
        # in both.
        sql = f"""
            SELECT m.*,
                   MAX(s.score) AS search_score,
                   {project_boost}
                   {recency_boost}
                   0 AS _dummy
            FROM (
                SELECT m.id AS mid, -bm25(memories_fts) AS score
                FROM   memories_fts
                JOIN   memories m ON memories_fts.rowid = m.rowid
                WHERE  memories_fts MATCH ? AND {where}
                UNION ALL
                SELECT c.memory_id AS mid, -bm25(memory_chunks_fts) AS score
                FROM   memory_chunks_fts
                JOIN   memory_chunks c ON memory_chunks_fts.rowid = c.rowid
                JOIN   memories m ON c.memory_id = m.id
                WHERE  memory_chunks_fts MATCH ? AND {where}
            ) s
            JOIN   memories m ON m.id = s.mid
            GROUP BY m.id
            ORDER BY {order_by_extra} search_score DESC
            LIMIT  ?
        """
        all_params = (
            [fts_query] + params
            + [fts_query] + params
            + project_boost_params
            + recency_boost_params
            + [limit]
        )
        rows = conn.execute(sql, all_params).fetchall()
        return [self._row_to_memory(r) for r in rows]

    def _search_fts5(
        self,
        conn: sqlite3.Connection,
        query: str,
        memory_type: MemoryType | None,
        project: str,
        scope: MemoryScope | None,
        tags: tuple[str, ...],
        limit: int,
        min_relevance: float,
        boost_project: str,
        recency_days: int,
    ) -> list[MemoryEntry]:
        try:
            conditions: list[str] = []
            params: list = []

            if memory_type:
                conditions.append("m.type = ?")
                params.append(memory_type.value)
            if project:
                conditions.append("m.project = ?")
                params.append(project)
            if scope:
                conditions.append("m.scope = ?")
                params.append(scope.value)
            if min_relevance > 0:
                conditions.append("m.relevance_score >= ?")
                params.append(min_relevance)
            if tags:
                tag_cond = self._build_tag_condition(conn, tags, params)
                if tag_cond:
                    conditions.append(tag_cond)

            where = " AND ".join(conditions) if conditions else "1=1"

            project_boost = ""
            project_boost_params: list = []
            if boost_project:
                project_boost = (
                    "CASE WHEN m.project = ? THEN 1 ELSE 0 END AS proj_match,"
                )
                project_boost_params = [boost_project]

            recency_boost = ""
            recency_boost_params: list = []
            if recency_days > 0:
                recency_boost = (
                    "CASE WHEN julianday('now') - julianday(m.created_at) <= ? "
                    "THEN 1 ELSE 0 END AS is_recent,"
                )
                recency_boost_params = [recency_days]

            order_by_extra = ""
            if boost_project and recency_days > 0:
                order_by_extra = "proj_match DESC, is_recent DESC,"
            elif boost_project:
                order_by_extra = "proj_match DESC,"
            elif recency_days > 0:
                order_by_extra = "is_recent DESC,"

            fts_query = self._escape_fts5_query(query)

            sql = f"""
                SELECT m.*,
                       -bm25(memories_fts) AS search_score,
                       {project_boost}
                       {recency_boost}
                       0 AS _dummy
                FROM   memories_fts
                JOIN   memories m ON memories_fts.rowid = m.rowid
                WHERE  memories_fts MATCH ? AND {where}
                ORDER BY {order_by_extra} search_score DESC
                LIMIT  ?
            """
            all_params = (
                [fts_query]
                + project_boost_params
                + recency_boost_params
                + params
                + [limit]
            )
            rows = conn.execute(sql, all_params).fetchall()
            return [self._row_to_memory(r) for r in rows]

        except sqlite3.OperationalError:
            return self._search_like(
                conn, query, memory_type, project, scope, tags,
                limit, min_relevance, boost_project, recency_days,
            )

    def _search_like(
        self,
        conn: sqlite3.Connection,
        query: str,
        memory_type: MemoryType | None,
        project: str,
        scope: MemoryScope | None,
        tags: tuple[str, ...],
        limit: int,
        min_relevance: float,
        boost_project: str,
        recency_days: int,
    ) -> list[MemoryEntry]:
        conditions: list[str] = []
        params: list = []

        if memory_type:
            conditions.append("type = ?")
            params.append(memory_type.value)
        if project:
            conditions.append("project = ?")
            params.append(project)
        if scope:
            conditions.append("scope = ?")
            params.append(scope.value)
        if min_relevance > 0:
            conditions.append("relevance_score >= ?")
            params.append(min_relevance)
        if tags:
            for tag in tags:
                conditions.append("INSTR(tags, ?) > 0")
                params.append(tag)
        if query:
            words = query.split()
            word_conds = []
            for w in words:
                word_conds.append("(INSTR(content, ?) > 0 OR INSTR(context, ?) > 0)")
                params.extend([w, w])
            conditions.append("(" + " OR ".join(word_conds) + ")")

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = (
            f"SELECT * FROM memories WHERE {where} "
            "ORDER BY relevance_score DESC, created_at DESC LIMIT ?"
        )
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        return [self._row_to_memory(r) for r in rows]

    def get_recent(self, limit: int = 10) -> list[MemoryEntry]:
        return self.search(limit=limit)

    def get_by_project(self, project: str, limit: int = 50) -> list[MemoryEntry]:
        return self.search(project=project, limit=limit)

    def get_by_type(self, mtype: MemoryType, limit: int = 50) -> list[MemoryEntry]:
        return self.search(memory_type=mtype, limit=limit)


    def decay_all(
        self,
        factor: float = 0.95,
        modifiers: dict[str, float] | None = None,
    ) -> int:
        total_deleted = 0
        last_id = ""

        while True:
            deleted, last_id = self._decay_page(factor, last_id, modifiers)
            total_deleted += deleted
            if last_id is None:
                break

        return total_deleted

    def _decay_page(
        self,
        factor: float,
        last_id: str,
        modifiers: dict[str, float] | None,
    ) -> tuple[int, str | None]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, relevance_score FROM memories WHERE id > ? "
                "ORDER BY id LIMIT ?",
                (last_id, _DECAY_PAGE_SIZE),
            ).fetchall()

            if not rows:
                return 0, None

            next_cursor = rows[-1]["id"]

            if modifiers:
                conn.execute("SAVEPOINT decay_page")
                for row in rows:
                    mid = row["id"]
                    effective_factor = factor * modifiers.get(mid, 1.0)
                    conn.execute(
                        """
                        UPDATE memories
                        SET    relevance_score = relevance_score * ?
                        WHERE  id = ? AND relevance_score > 0.01
                        """,
                        (effective_factor, mid),
                    )
                conn.execute("RELEASE SAVEPOINT decay_page")
            else:
                ids = [r["id"] for r in rows]
                placeholders = ",".join("?" * len(ids))
                conn.execute(
                    f"""
                    UPDATE memories
                    SET    relevance_score = relevance_score * ?
                    WHERE  id IN ({placeholders}) AND relevance_score > 0.01
                    """,
                    [factor] + ids,
                )

            ids = [r["id"] for r in rows]
            placeholders = ",".join("?" * len(ids))
            cur = conn.execute(
                f"DELETE FROM memories WHERE id IN ({placeholders}) "
                "AND relevance_score < 0.01",
                ids,
            )
            deleted = cur.rowcount
            conn.commit()

        return deleted, next_cursor


    def save_embedding(self, memory_id: str, embedding: list[float], model_name: str) -> None:
        blob = struct.pack(f"{len(embedding)}f", *embedding)
        with self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO memory_embeddings
                    (memory_id, embedding, model_name, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (memory_id, blob, model_name, datetime.now(timezone.utc).isoformat()),
                )
                conn.commit()
            except sqlite3.OperationalError:
                pass  # Table not yet created (pre-v12 database).

    def get_embedding(self, memory_id: str) -> list[float] | None:
        with self._connect() as conn:
            try:
                row = conn.execute(
                    "SELECT embedding FROM memory_embeddings WHERE memory_id = ?",
                    (memory_id,),
                ).fetchone()
            except sqlite3.OperationalError:
                return None
        if not row:
            return None
        blob: bytes = row["embedding"]
        n = len(blob) // 4  # 4 bytes per float32
        return list(struct.unpack(f"{n}f", blob))

    def search_semantic(
        self,
        query: str | list[float],
        limit: int = 20,
        project: str = "",
    ) -> list[tuple[float, MemoryEntry]]:
        if isinstance(query, str):
            if not EmbeddingEngine.AVAILABLE:
                return []
            try:
                query_embedding = EmbeddingEngine.embed(query)
            except Exception as e:
                logger.error("Failed to embed query for semantic search: %s", e)
                return []
        else:
            query_embedding = query

        with self._connect() as conn:
            try:
                rows = conn.execute(
                    "SELECT memory_id, embedding FROM memory_embeddings"
                ).fetchall()
            except sqlite3.OperationalError:
                return []

        if not rows:
            return []

        candidates: list[tuple[float, str]] = []
        q = query_embedding
        q_len = len(q)

        for row in rows:
            blob: bytes = row["embedding"]
            n = len(blob) // 4
            if n != q_len:
                continue
            vec = struct.unpack(f"{n}f", blob)
            dot = sum(a * b for a, b in zip(q, vec))
            candidates.append((dot, row["memory_id"]))

        # Sort by similarity descending.
        candidates.sort(key=lambda x: x[0], reverse=True)
        top = candidates[:limit * 3]  # over-fetch to account for project filter

        results: list[tuple[float, MemoryEntry]] = []
        with self._connect() as conn:
            for score, mid in top:
                row = conn.execute(
                    "SELECT * FROM memories WHERE id = ?", (mid,)
                ).fetchone()
                if row is None:
                    continue
                mem = self._row_to_memory(row)
                if project and mem.project != project:
                    continue
                results.append((score, mem))
                if len(results) >= limit:
                    break

        return results


    def save_session(self, session: SessionSnapshot) -> SessionSnapshot:
        with self._connect() as conn:
            execute_with_retry(
                conn,
                """
                INSERT OR REPLACE INTO sessions
                (session_id, project, summary, key_decisions, tools_used,
                 errors_encountered, started_at, ended_at, input_tokens,
                 output_tokens, memory_ids)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.session_id,
                    session.project,
                    session.summary,
                    json.dumps(list(session.key_decisions)),
                    json.dumps(list(session.tools_used)),
                    json.dumps(list(session.errors_encountered)),
                    session.started_at.isoformat(),
                    session.ended_at.isoformat() if session.ended_at else None,
                    session.input_tokens,
                    session.output_tokens,
                    json.dumps(list(session.memory_ids_extracted)),
                ),
            )
            conn.commit()
        return session

    def get_session(self, session_id: str) -> SessionSnapshot | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        if not row:
            return None
        return self._session_row_to_snapshot(row)

    def get_sessions(self, project: str = "", limit: int = 20) -> list[SessionSnapshot]:
        with self._connect() as conn:
            if project:
                rows = conn.execute(
                    "SELECT * FROM sessions WHERE project = ? "
                    "ORDER BY started_at DESC LIMIT ?",
                    (project, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?", (limit,)
                ).fetchall()
        return [self._session_row_to_snapshot(r) for r in rows]


    @staticmethod
    def _session_row_to_snapshot(row: sqlite3.Row) -> SessionSnapshot:
        from datetime import datetime as _dt

        return SessionSnapshot(
            session_id=row["session_id"],
            project=row["project"],
            summary=row["summary"],
            key_decisions=tuple(json.loads(row["key_decisions"])),
            tools_used=tuple(json.loads(row["tools_used"])),
            errors_encountered=tuple(json.loads(row["errors_encountered"])),
            started_at=_dt.fromisoformat(row["started_at"]),
            ended_at=_dt.fromisoformat(row["ended_at"]) if row["ended_at"] else None,
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            memory_ids_extracted=tuple(json.loads(row["memory_ids"])),
        )

    @staticmethod
    def _safe_get_row(row: sqlite3.Row, key: str, default: Any = None) -> Any:
        try:
            val = row[key]
            return val if val is not None else default
        except (IndexError, KeyError):
            return default

    @staticmethod
    def _row_to_memory(row: sqlite3.Row) -> MemoryEntry:
        from datetime import datetime as _dt

        return MemoryEntry(
            id=row["id"],
            type=MemoryType(row["type"]),
            scope=MemoryScope(row["scope"]),
            content=row["content"],
            context=row["context"] or "",
            relevance_score=row["relevance_score"],
            created_at=_dt.fromisoformat(row["created_at"]),
            last_accessed=(
                _dt.fromisoformat(row["last_accessed"])
                if row["last_accessed"] else None
            ),
            access_count=row["access_count"],
            project=row["project"] or "",
            tags=tuple(json.loads(row["tags"])),
            gist=MemoryStore._safe_get_row(row, "gist", ""),
        )
