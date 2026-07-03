
from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from .store import MemoryStore

logger = logging.getLogger(__name__)


class MemoryConsolidator:

    @classmethod
    def consolidate(
        cls,
        store: MemoryStore,
        project: str = "",
        min_cluster_size: int = 5,
    ) -> list[dict[str, Any]]:
        memories = store.search(project=project, limit=5000)

        groups: dict[tuple[str, str], list[str]] = {}
        memories_by_id = {m.id: m for m in memories}

        for m in memories:
            for tag in m.tags:
                key = (m.project, tag)
                groups.setdefault(key, []).append(m.id)

        created_clusters = []
        now_str = datetime.now(timezone.utc).isoformat()

        with store._connect() as conn:
            for (proj, tag), ids in groups.items():
                if len(ids) < min_cluster_size:
                    continue

                theme = f"Consolidated memories under tag '{tag}'"

                contents = []
                for mid in ids:
                    m = memories_by_id[mid]
                    first_sentence = m.content.split(".")[0].strip()
                    if not first_sentence.endswith("."):
                        first_sentence += "."
                    contents.append(first_sentence)
                summary = " ".join(contents)

                cluster_id = uuid.uuid4().hex[:12]

                try:
                    existing = conn.execute(
                        "SELECT cluster_id FROM memory_clusters WHERE project = ? AND theme = ? LIMIT 1",
                        (proj, theme),
                    ).fetchone()
                except sqlite3.OperationalError:
                    # Table not yet migrated
                    continue

                if existing:
                    cid = existing["cluster_id"]
                    conn.execute(
                        """
                        UPDATE memory_clusters
                        SET    summary = ?,
                               source_memory_ids = ?,
                               last_updated = ?
                        WHERE  cluster_id = ?
                        """,
                        (summary, json.dumps(ids), now_str, cid),
                    )
                    cluster_id = cid
                else:
                    conn.execute(
                        """
                        INSERT INTO memory_clusters
                        (cluster_id, project, theme, summary, source_memory_ids, created_at, last_updated, confidence)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 1.0)
                        """,
                        (
                            cluster_id,
                            proj,
                            theme,
                            summary,
                            json.dumps(ids),
                            now_str,
                            now_str,
                        ),
                    )

                # Accelerate decay for clustered episodic memories: half their relevance
                placeholders = ",".join("?" * len(ids))
                conn.execute(
                    f"UPDATE memories SET relevance_score = relevance_score * 0.5 WHERE id IN ({placeholders})",
                    ids,
                )

                created_clusters.append(
                    {
                        "cluster_id": cluster_id,
                        "project": proj,
                        "theme": theme,
                        "summary": summary,
                        "source_memory_ids": ids,
                    }
                )

            conn.commit()

        return created_clusters

    @classmethod
    def promote_cluster_to_schema(
        cls,
        cluster_id: str,
        store: MemoryStore,
        force: bool = False,
    ) -> dict[str, Any] | None:
        with store._connect() as conn:
            try:
                row = conn.execute(
                    "SELECT * FROM memory_clusters WHERE cluster_id = ?",
                    (cluster_id,),
                ).fetchone()
            except sqlite3.OperationalError:
                return None

            if not row:
                return None

            # Stability rules: confidence >= 0.8 and age >= 30 days
            last_updated = datetime.fromisoformat(row["last_updated"])
            age = datetime.now(timezone.utc) - last_updated
            confidence = row["confidence"] or 1.0

            if not force:
                if age < timedelta(days=30) or confidence < 0.8:
                    logger.debug(
                        "Cluster %s is not yet stable enough for promotion (age=%s, confidence=%s)",
                        cluster_id,
                        age,
                        confidence,
                    )
                    return None

            schema_id = uuid.uuid4().hex[:12]
            name = f"Procedural Schema: {row['theme']}"
            description = row["summary"]
            source_cluster_ids = json.dumps([cluster_id])
            now_str = datetime.now(timezone.utc).isoformat()

            existing = conn.execute(
                "SELECT schema_id FROM memory_schemas WHERE project = ? AND name = ? LIMIT 1",
                (row["project"], name),
            ).fetchone()

            if existing:
                sid = existing["schema_id"]
                conn.execute(
                    """
                    UPDATE memory_schemas
                    SET    description = ?,
                           source_cluster_ids = ?,
                           last_verified = ?
                    WHERE  schema_id = ?
                    """,
                    (description, source_cluster_ids, now_str, sid),
                )
                schema_id = sid
            else:
                conn.execute(
                    """
                    INSERT INTO memory_schemas
                    (schema_id, project, name, description, source_cluster_ids, created_at, last_verified)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        schema_id,
                        row["project"],
                        name,
                        description,
                        source_cluster_ids,
                        now_str,
                        now_str,
                    ),
                )

            conn.commit()

            return {
                "schema_id": schema_id,
                "project": row["project"],
                "name": name,
                "description": description,
                "source_cluster_ids": [cluster_id],
            }
