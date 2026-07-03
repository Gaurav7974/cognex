
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from cognex.models import MemoryEntry, StateUnit
from cognex.ledger import DecisionEntry

logger = logging.getLogger(__name__)


class DeltaComputer:

    @classmethod
    def compute_vector_clock(cls, store, ledger, unit_store) -> dict[str, str]:
        clock = {
            "memories": "1970-01-01T00:00:00Z",
            "decisions": "1970-01-01T00:00:00Z",
            "cognitive_units": "1970-01-01T00:00:00Z",
        }

        try:
            with store._connect() as conn:
                row = conn.execute("SELECT MAX(created_at) FROM memories").fetchone()
                if row and row[0]:
                    clock["memories"] = row[0]
        except Exception:
            pass

        try:
            with ledger._pool.get_connection() as conn:
                row = conn.execute("SELECT MAX(timestamp) FROM decisions").fetchone()
                if row and row[0]:
                    clock["decisions"] = row[0]
        except Exception:
            pass

        try:
            with unit_store._pool.get_connection() as conn:
                row = conn.execute(
                    "SELECT MAX(created_at) FROM cognitive_units"
                ).fetchone()
                if row and row[0]:
                    clock["cognitive_units"] = row[0]
        except Exception:
            pass

        return clock

    @classmethod
    def compute_delta(
        cls, store, ledger, unit_store, since_timestamp: str
    ) -> dict[str, list[dict[str, Any]]]:
        delta = {"memories": [], "decisions": [], "cognitive_units": []}

        try:
            with store._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM memories WHERE created_at > ?",
                    (since_timestamp,),
                ).fetchall()
                delta["memories"] = [
                    store._row_to_memory(r).as_dict() for r in rows
                ]
        except Exception as e:
            logger.error("Failed to compute memories delta: %s", e)

        try:
            with ledger._pool.get_connection() as conn:
                rows = conn.execute(
                    "SELECT * FROM decisions WHERE timestamp > ?",
                    (since_timestamp,),
                ).fetchall()
                # Resolve row to DecisionEntry manually to avoid circular import issues
                for r in rows:
                    entry = DecisionEntry.from_dict(
                        {
                            "id": r["id"],
                            "tool_used": r["tool_used"],
                            "alternatives": json_loads(r["alternatives"]),
                            "reasoning": r["reasoning"],
                            "context": r["context"],
                            "project": r["project"],
                            "outcome": r["outcome"],
                            "outcome_success": r["outcome_success"],
                            "timestamp": r["timestamp"],
                            "session_id": r["session_id"],
                            "tags": json_loads(r["tags"]),
                        }
                    )
                    delta["decisions"].append(entry.as_dict())
        except Exception as e:
            logger.error("Failed to compute decisions delta: %s", e)

        try:
            with unit_store._pool.get_connection() as conn:
                rows = conn.execute(
                    "SELECT * FROM cognitive_units WHERE created_at > ?",
                    (since_timestamp,),
                ).fetchall()
                for r in rows:
                    entry = StateUnit(
                        unit_id=r["unit_id"],
                        unit_type=r["unit_type"],
                        content=r["content"],
                        rationale=r["rationale"],
                        scope=r["scope"],
                        confidence=r["confidence"],
                        tags=json_loads(r["tags"]),
                        created_at=datetime.fromisoformat(r["created_at"]),
                        session_id=r["session_id"],
                        project=r["project"],
                        override_count=r["override_count"],
                        last_verified=datetime.fromisoformat(r["last_verified"])
                        if r["last_verified"]
                        else None,
                    )
                    delta["cognitive_units"].append(entry.as_dict())
        except Exception as e:
            logger.error("Failed to compute cognitive_units delta: %s", e)

        return delta

    @classmethod
    def apply_delta(
        cls, store, ledger, unit_store, audit, delta: dict[str, list[dict[str, Any]]]
    ) -> dict[str, int]:
        stats = {"memories": 0, "decisions": 0, "cognitive_units": 0, "conflicts": 0}

        for m_dict in delta.get("memories", []):
            remote_mem = MemoryEntry.from_dict(m_dict)
            local_mem = store.get(remote_mem.id)

            if local_mem:
                winner = MergeResolver.resolve_memory_conflict(
                    local_mem, remote_mem
                )
                if winner == remote_mem:
                    store.delete(local_mem.id)
                    store.save(remote_mem)
                    audit.append(
                        event_type="sync_merge_conflict",
                        payload={
                            "type": "memory",
                            "id": remote_mem.id,
                            "action": "overwritten",
                        },
                    )
                    stats["conflicts"] += 1
                    stats["memories"] += 1
            else:
                store.save(remote_mem)
                stats["memories"] += 1

        for d_dict in delta.get("decisions", []):
            remote_dec = DecisionEntry.from_dict(d_dict)
            local_dec = ledger.get(remote_dec.id)

            if local_dec:
                winner = MergeResolver.resolve_decision_conflict(
                    local_dec, remote_dec
                )
                if winner == remote_dec:
                    ledger._save(remote_dec)
                    audit.append(
                        event_type="sync_merge_conflict",
                        payload={
                            "type": "decision",
                            "id": remote_dec.id,
                            "action": "overwritten",
                        },
                    )
                    stats["conflicts"] += 1
                    stats["decisions"] += 1
            else:
                ledger._save(remote_dec)
                stats["decisions"] += 1

        for u_dict in delta.get("cognitive_units", []):
            remote_unit = StateUnit(
                unit_id=u_dict["unit_id"],
                unit_type=u_dict["unit_type"],
                content=u_dict["content"],
                rationale=u_dict.get("rationale", ""),
                scope=u_dict.get("scope", ""),
                confidence=u_dict.get("confidence", 1.0),
                tags=tuple(u_dict.get("tags", [])),
                created_at=datetime.fromisoformat(u_dict["created_at"]),
                session_id=u_dict.get("session_id", ""),
                project=u_dict.get("project", ""),
                override_count=u_dict.get("override_count", 0),
                last_verified=datetime.fromisoformat(u_dict["last_verified"])
                if u_dict.get("last_verified")
                else None,
            )
            local_unit = unit_store.get(remote_unit.unit_id)

            if local_unit:
                winner = MergeResolver.resolve_unit_conflict(
                    local_unit, remote_unit
                )
                if winner == remote_unit:
                    unit_store.save(remote_unit)
                    audit.append(
                        event_type="sync_merge_conflict",
                        payload={
                            "type": "cognitive_unit",
                            "id": remote_unit.unit_id,
                            "action": "overwritten",
                        },
                    )
                    stats["conflicts"] += 1
                    stats["cognitive_units"] += 1
            else:
                unit_store.save(remote_unit)
                stats["cognitive_units"] += 1

        return stats


def json_loads(val: Any) -> Any:
    if not val:
        return []
    try:
        return json.loads(val)
    except Exception:
        return []


class MergeResolver:

    @classmethod
    def resolve_memory_conflict(
        cls, local: MemoryEntry, remote: MemoryEntry
    ) -> MemoryEntry:
        if remote.created_at > local.created_at:
            return remote
        if remote.created_at < local.created_at:
            return local
        # Equal timestamps: higher score wins
        return remote if remote.relevance_score >= local.relevance_score else local

    @classmethod
    def resolve_unit_conflict(
        cls, local: StateUnit, remote: StateUnit
    ) -> StateUnit:
        if remote.confidence > local.confidence:
            return remote
        if remote.confidence < local.confidence:
            return local
        # Equal confidence: lower override count wins
        return remote if remote.override_count <= local.override_count else local

    @classmethod
    def resolve_decision_conflict(
        cls, local: DecisionEntry, remote: DecisionEntry
    ) -> DecisionEntry:
        if remote.timestamp >= local.timestamp:
            return remote
        return local
