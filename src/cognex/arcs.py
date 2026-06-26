"""Session Arc Manager for grouping related sessions over time.

This module supports temporal context windows (session arcs) to track
multi-session progress narratives and help agents maintain context over
days or weeks of separate sessions.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from .store import MemoryStore

logger = logging.getLogger(__name__)


class SessionArcManager:
    """Manages session arcs to represent multi-session context narratives."""

    @classmethod
    def get_or_create_arc(
        cls, session_id: str, project: str, store: MemoryStore
    ) -> dict[str, Any]:
        """Find the most recent active arc for a project within 7 days, or create one."""
        now = datetime.now(timezone.utc)
        now_str = now.isoformat()

        with store._connect() as conn:
            # Find the most recent active arc for project
            try:
                row = conn.execute(
                    """
                    SELECT * FROM session_arcs
                    WHERE  project = ? AND status = 'active'
                    ORDER BY last_session_at DESC LIMIT 1
                    """,
                    (project,),
                ).fetchone()
            except sqlite3.OperationalError:
                # Table not yet migrated
                row = None

            if row:
                last_session_at = datetime.fromisoformat(row["last_session_at"])
                if now - last_session_at <= timedelta(days=7):
                    # Within 7 days, append session_id
                    session_ids = json.loads(row["session_ids"])
                    if session_id and session_id not in session_ids:
                        session_ids.append(session_id)

                    conn.execute(
                        """
                        UPDATE session_arcs
                        SET    session_ids = ?,
                               last_session_at = ?
                        WHERE  arc_id = ?
                        """,
                        (json.dumps(session_ids), now_str, row["arc_id"]),
                    )
                    conn.commit()

                    return {
                        "arc_id": row["arc_id"],
                        "project": project,
                        "session_ids": session_ids,
                        "started_at": row["started_at"],
                        "last_session_at": now_str,
                        "status": "active",
                    }

            # Create new arc
            arc_id = uuid.uuid4().hex[:12]
            session_ids = [session_id] if session_id else []
            try:
                conn.execute(
                    """
                    INSERT INTO session_arcs
                    (arc_id, project, session_ids, started_at, last_session_at, status)
                    VALUES (?, ?, ?, ?, ?, 'active')
                    """,
                    (arc_id, project, json.dumps(session_ids), now_str, now_str),
                )
                conn.commit()
            except sqlite3.OperationalError:
                pass  # Fallback if table doesn't exist yet

            return {
                "arc_id": arc_id,
                "project": project,
                "session_ids": session_ids,
                "started_at": now_str,
                "last_session_at": now_str,
                "status": "active",
            }

    @classmethod
    def close_arc(cls, arc_id: str, store: MemoryStore) -> bool:
        """Mark an arc as closed and compile its final summary narrative."""
        summary = cls.summarize_arc(arc_id, store)
        with store._connect() as conn:
            try:
                cur = conn.execute(
                    """
                    UPDATE session_arcs
                    SET    status = 'closed',
                           arc_summary = ?
                    WHERE  arc_id = ?
                    """,
                    (summary, arc_id),
                )
                conn.commit()
                return cur.rowcount > 0
            except sqlite3.OperationalError:
                return False

    @classmethod
    def get_active_arc(cls, project: str, store: MemoryStore) -> dict[str, Any] | None:
        """Get the current active session arc for a project."""
        with store._connect() as conn:
            try:
                row = conn.execute(
                    """
                    SELECT * FROM session_arcs
                    WHERE  project = ? AND status = 'active'
                    ORDER BY last_session_at DESC LIMIT 1
                    """,
                    (project,),
                ).fetchone()
            except sqlite3.OperationalError:
                return None

        if not row:
            return None

        return {
            "arc_id": row["arc_id"],
            "project": row["project"],
            "arc_summary": row["arc_summary"] or "",
            "session_ids": json.loads(row["session_ids"]),
            "started_at": row["started_at"],
            "last_session_at": row["last_session_at"],
            "cumulative_decisions": json.loads(row["cumulative_decisions"] or "[]"),
            "known_blockers": json.loads(row["known_blockers"] or "[]"),
            "status": row["status"],
        }

    @classmethod
    def summarize_arc(cls, arc_id: str, store: MemoryStore) -> str:
        """Compile a narrative combining all session summaries in this arc."""
        with store._connect() as conn:
            try:
                row = conn.execute(
                    "SELECT session_ids, project FROM session_arcs WHERE arc_id = ?",
                    (arc_id,),
                ).fetchone()
            except sqlite3.OperationalError:
                return "Arc table not found."

            if not row:
                return "Arc not found."

            session_ids = json.loads(row["session_ids"])
            if not session_ids:
                return "No sessions in this arc."

            placeholders = ",".join("?" * len(session_ids))
            sessions = conn.execute(
                f"SELECT session_id, summary, started_at FROM sessions WHERE session_id IN ({placeholders}) ORDER BY started_at ASC",
                session_ids,
            ).fetchall()

        if not sessions:
            return f"No session summaries found for sessions in arc {arc_id}."

        narrative = [f"Work Arc summary for project '{row['project']}':"]
        for s in sessions:
            started = s["started_at"].split("T")[0]
            summary = s["summary"] or "No summary provided."
            narrative.append(f"- [{started}] Session {s['session_id']}: {summary}")

        return "\n".join(narrative)
