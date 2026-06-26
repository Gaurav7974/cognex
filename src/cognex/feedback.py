"""Outcome feedback and semantic decay modifier calculations.

Allows the system to adjust memory relevance scores retroactively based on
the success or failure of decisions made in a session, and to adjust decay rates
based on how semantically unique a memory is.
"""

from __future__ import annotations

import logging
import sqlite3
import struct
from datetime import datetime, timezone

from .store import MemoryStore

logger = logging.getLogger(__name__)


class OutcomeFeedback:
    """Retroactively adjusts memory relevance based on outcome success."""

    @classmethod
    def apply_outcome_feedback(
        cls,
        session_id: str,
        success: bool,
        store: MemoryStore,
        ledger,
        audit,
    ) -> None:
        """Trace memories accessed in session_id and adjust their relevance."""
        if not session_id or session_id == "unknown":
            return

        with store._connect() as conn:
            try:
                rows = conn.execute(
                    "SELECT DISTINCT memory_id FROM memory_access_log WHERE session_id = ?",
                    (session_id,),
                ).fetchall()
            except sqlite3.OperationalError:
                # Table doesn't exist yet (pre-v13 database)
                return

        if not rows:
            logger.debug("No memories accessed in session %s for feedback", session_id)
            return

        memory_ids = [r["memory_id"] for r in rows]

        # Apply adjustments
        delta = 0.05 if success else 0.03
        for mid in memory_ids:
            if success:
                store.boost_relevance(mid, delta=delta)
            else:
                store.penalize_relevance(mid, delta=delta)

        # Log to audit log
        try:
            audit.append(
                event_type="outcome_feedback",
                session_id=session_id,
                payload={
                    "memory_ids": memory_ids,
                    "success": success,
                    "adjustment_delta": delta,
                },
            )
        except Exception as e:
            logger.error("Failed to write audit log for outcome feedback: %s", e)

    @classmethod
    def compute_uniqueness_modifiers(
        cls, store: MemoryStore, project: str = ""
    ) -> dict[str, float]:
        """Compute per-memory decay modifiers based on semantic uniqueness.

        Unique memories (low similarity to neighbors) decay slower (modifier < 1.0).
        Redundant memories (high similarity to neighbors) decay faster (modifier > 1.0).
        """
        from .embeddings import EmbeddingEngine

        if not EmbeddingEngine.AVAILABLE:
            return {}

        with store._connect() as conn:
            try:
                if project:
                    rows = conn.execute(
                        """
                        SELECT me.memory_id, me.embedding 
                        FROM   memory_embeddings me
                        JOIN   memories m ON me.memory_id = m.id
                        WHERE  m.project = ?
                        """,
                        (project,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT memory_id, embedding FROM memory_embeddings"
                    ).fetchall()
            except sqlite3.OperationalError:
                return {}

        if len(rows) < 10:
            # Not enough memories to compute meaningful density/similarity
            return {}

        # Unpack all embeddings
        embeddings = {}
        for r in rows:
            blob: bytes = r["embedding"]
            n = len(blob) // 4
            if n != 384:  # miniLM dimension
                continue
            vec = struct.unpack(f"{n}f", blob)
            embeddings[r["memory_id"]] = vec

        modifiers = {}
        mids = list(embeddings.keys())

        for i, mid in enumerate(mids):
            q = embeddings[mid]
            similarities = []
            for j, other_id in enumerate(mids):
                if i == j:
                    continue
                other_vec = embeddings[other_id]
                # Dot product is cosine similarity because they are normalized
                sim = sum(a * b for a, b in zip(q, other_vec))
                similarities.append(sim)

            if not similarities:
                continue

            # Find similarity to 5 nearest neighbors
            similarities.sort(reverse=True)
            k = min(5, len(similarities))
            avg_sim = sum(similarities[:k]) / k

            # Map avg_sim to modifier in [0.85, 1.05]
            # Standard cosine similarity is in [-1, 1]. For sentence embeddings, it's usually [0.2, 0.8].
            # Linear interpolation from:
            #   avg_sim <= 0.3 -> 0.85 (unique, decays slower)
            #   avg_sim >= 0.7 -> 1.05 (redundant, decays faster)
            if avg_sim <= 0.3:
                mod = 0.85
            elif avg_sim >= 0.7:
                mod = 1.05
            else:
                mod = 0.85 + (avg_sim - 0.3) * 0.20 / 0.40
            modifiers[mid] = round(mod, 4)

        return modifiers
