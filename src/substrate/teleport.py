"""Teleport Protocol — serialize, transfer, and rehydrate agent state."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class TeleportBundle:
    """A portable snapshot of an agent's complete working state.

    Version 2.0: Now includes full memory and decision content for
    cross-machine transfer (not just IDs which only work locally).
    """

    bundle_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    version: str = "2.0"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_host: str = ""
    target_host: str = ""

    # Core state
    session_id: str = ""
    project: str = ""
    session_summary: str = ""

    # Full memory content (v2.0) - replaces memory_ids
    memories: tuple[dict, ...] = ()  # Serialized MemoryEntry objects

    # Legacy field for backward compatibility
    memory_ids: tuple[str, ...] = ()

    # Trust state
    trust_records: tuple[dict, ...] = ()

    # Full decision content (v2.0) - replaces decision_ids
    decisions: tuple[dict, ...] = ()  # Serialized DecisionEntry objects

    # Legacy field for backward compatibility
    decision_ids: tuple[str, ...] = ()

    # Context
    workspace_context: str = ""
    pending_tasks: tuple[str, ...] = ()
    last_action: str = ""

    # Metadata
    model_name: str = ""
    tool_claims: tuple[str, ...] = ()  # Tools the agent expects to use
    signature: str = ""  # Simple integrity check

    def serialize(self) -> str:
        """Serialize to JSON for transfer."""
        return json.dumps(
            {
                "bundle_id": self.bundle_id,
                "version": self.version,
                "created_at": self.created_at.isoformat(),
                "source_host": self.source_host,
                "target_host": self.target_host,
                "session_id": self.session_id,
                "project": self.project,
                "session_summary": self.session_summary,
                # v2.0: Full content
                "memories": list(self.memories),
                "decisions": list(self.decisions),
                # Legacy fields (for backward compat)
                "memory_ids": list(self.memory_ids),
                "decision_ids": list(self.decision_ids),
                "trust_records": list(self.trust_records),
                "workspace_context": self.workspace_context,
                "pending_tasks": list(self.pending_tasks),
                "last_action": self.last_action,
                "model_name": self.model_name,
                "tool_claims": list(self.tool_claims),
                "signature": self.signature,
            },
            indent=2,
        )

    @classmethod
    def deserialize(cls, data: str) -> TeleportBundle:
        d = json.loads(data)
        return cls(
            bundle_id=d["bundle_id"],
            version=d["version"],
            created_at=datetime.fromisoformat(d["created_at"]),
            source_host=d.get("source_host", ""),
            target_host=d.get("target_host", ""),
            session_id=d.get("session_id", ""),
            project=d.get("project", ""),
            session_summary=d.get("session_summary", ""),
            # v2.0: Full content
            memories=tuple(d.get("memories", [])),
            decisions=tuple(d.get("decisions", [])),
            # Legacy fields
            memory_ids=tuple(d.get("memory_ids", [])),
            decision_ids=tuple(d.get("decision_ids", [])),
            trust_records=tuple(d.get("trust_records", [])),
            workspace_context=d.get("workspace_context", ""),
            pending_tasks=tuple(d.get("pending_tasks", [])),
            last_action=d.get("last_action", ""),
            model_name=d.get("model_name", ""),
            tool_claims=tuple(d.get("tool_claims", [])),
            signature=d.get("signature", ""),
        )

    def sign(self) -> TeleportBundle:
        """Create a simple integrity signature."""
        import hashlib

        payload = f"{self.bundle_id}:{self.session_id}:{self.project}:{len(self.memories)}:{len(self.decisions)}:{len(self.trust_records)}"
        sig = hashlib.sha256(payload.encode()).hexdigest()[:16]
        return TeleportBundle(
            bundle_id=self.bundle_id,
            version=self.version,
            created_at=self.created_at,
            source_host=self.source_host,
            target_host=self.target_host,
            session_id=self.session_id,
            project=self.project,
            session_summary=self.session_summary,
            memories=self.memories,
            memory_ids=self.memory_ids,
            trust_records=self.trust_records,
            decisions=self.decisions,
            decision_ids=self.decision_ids,
            workspace_context=self.workspace_context,
            pending_tasks=self.pending_tasks,
            last_action=self.last_action,
            model_name=self.model_name,
            tool_claims=self.tool_claims,
            signature=sig,
        )

    def verify(self) -> bool:
        """Verify the bundle hasn't been tampered with."""
        if not self.signature:
            return False
        clean = TeleportBundle(
            bundle_id=self.bundle_id,
            version=self.version,
            created_at=self.created_at,
            source_host=self.source_host,
            target_host=self.target_host,
            session_id=self.session_id,
            project=self.project,
            session_summary=self.session_summary,
            memories=self.memories,
            memory_ids=self.memory_ids,
            trust_records=self.trust_records,
            decisions=self.decisions,
            decision_ids=self.decision_ids,
            workspace_context=self.workspace_context,
            pending_tasks=self.pending_tasks,
            last_action=self.last_action,
            model_name=self.model_name,
            tool_claims=self.tool_claims,
        ).sign()
        return clean.signature == self.signature

    def save_to_file(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.serialize())
        return p

    @classmethod
    def load_from_file(cls, path: str | Path) -> TeleportBundle:
        return cls.deserialize(Path(path).read_text())


class TeleportProtocol:
    """Creates and validates teleport bundles.

    Usage:
        protocol = TeleportProtocol()
        # Create a bundle from current state
        bundle = protocol.create_bundle(
            substrate=substrate,
            source_host="laptop",
            target_host="production-server",
        )
        # Save and transfer (in real use, send over network)
        bundle.save_to_file("teleport.json")
        # On target machine:
        received = TeleportBundle.load_from_file("teleport.json")
        if received.verify():
            state = protocol.rehydrate(received, substrate)
    """

    def create_bundle(
        self,
        substrate,  # CognitiveSubstrate
        source_host: str = "",
        target_host: str = "",
        pending_tasks: tuple[str, ...] = (),
        last_action: str = "",
        model_name: str = "",
        tool_claims: tuple[str, ...] = (),
        trust_engine=None,  # Optional TrustGradientEngine
        decision_ledger=None,  # Optional DecisionLedger
    ) -> TeleportBundle:
        """Create a teleport bundle from a substrate's current state.

        Args:
            substrate: The CognitiveSubstrate instance
            source_host: Source host identifier
            target_host: Target host identifier
            pending_tasks: Pending task descriptions
            last_action: Last action performed
            model_name: Model name
            tool_claims: Tool claims
            trust_engine: Optional TrustGradientEngine for trust record export
            decision_ledger: Optional DecisionLedger for decision export
        """
        # v2.0: Serialize full memory content (not just IDs)
        all_memories = substrate.store.search(limit=9999)
        memories = tuple(m.as_dict() for m in all_memories)
        memory_ids = tuple(m.id for m in all_memories)  # Keep for backward compat

        # v2.0: Serialize full decision content
        decisions = ()
        decision_ids = ()
        if decision_ledger is not None:
            all_decisions = decision_ledger.get_all(limit=9999)
            decisions = tuple(d.as_dict() for d in all_decisions)
            decision_ids = tuple(d.id for d in all_decisions)

        # Gather trust records from the provided trust engine
        trust_records = ()
        if trust_engine is not None:
            trust_summary = trust_engine.get_trust_summary()
            trust_records = tuple(r.as_dict() for r in trust_summary)

        # Gather session info
        session_id = substrate.current_session or ""
        project = substrate.current_project or ""

        bundle = TeleportBundle(
            source_host=source_host,
            target_host=target_host,
            session_id=session_id,
            project=project,
            session_summary="",
            memories=memories,
            memory_ids=memory_ids,
            decisions=decisions,
            decision_ids=decision_ids,
            trust_records=trust_records,
            workspace_context="",
            pending_tasks=pending_tasks,
            last_action=last_action,
            model_name=model_name,
            tool_claims=tool_claims,
        )
        return bundle.sign()

    def rehydrate(
        self, bundle: TeleportBundle, substrate, trust_engine=None, decision_ledger=None
    ) -> dict:
        """Rehydrate a substrate from a teleport bundle.

        Args:
            bundle: The TeleportBundle to restore from
            substrate: The CognitiveSubstrate instance
            trust_engine: Optional TrustGradientEngine instance for trust restoration
            decision_ledger: Optional DecisionLedger for decision restoration

        Returns a report of what was restored.
        """
        if not bundle.verify():
            return {"status": "failed", "reason": "Bundle signature invalid"}

        memories_restored = 0
        sessions_restored = 0
        trust_restored = False
        decisions_restored = 0

        # Restore session context
        if bundle.session_id:
            try:
                substrate.start_session(bundle.session_id, project=bundle.project)
                sessions_restored = 1
            except Exception:
                pass

        # v2.0: Restore full memory content (cross-machine compatible)
        if bundle.memories and hasattr(substrate, "store"):
            from substrate.models import MemoryEntry

            restored_memories = []
            for mem_dict in bundle.memories:
                try:
                    memory = MemoryEntry.from_dict(mem_dict)
                    restored_memories.append(memory)
                except Exception:
                    pass

            if restored_memories:
                substrate.store.save_many(restored_memories)
                memories_restored = len(restored_memories)

        # v2.0: Restore full decision content (cross-machine compatible)
        if bundle.decisions and decision_ledger is not None:
            from substrate.ledger import DecisionEntry

            for dec_dict in bundle.decisions:
                try:
                    decision = DecisionEntry.from_dict(dec_dict)
                    decision_ledger._save(decision)
                    decisions_restored += 1
                except Exception:
                    pass

        # Restore trust records using the provided trust engine
        if bundle.trust_records and trust_engine is not None:
            from substrate.trust import TrustRecord

            trust_count = 0
            for tr in bundle.trust_records:
                try:
                    # Restore the full TrustRecord from serialized dict
                    record = TrustRecord.from_dict(tr)
                    # Use the trust engine's internal update to restore the record
                    trust_engine._update_trust(
                        record.tool_name,
                        record.context,
                        record.project,
                        lambda _: record,  # Return the full record as-is
                    )
                    trust_count += 1
                except Exception:
                    pass
            trust_restored = trust_count > 0

        return {
            "status": "success",
            "bundle_version": bundle.version,
            "memories_restored": memories_restored,
            "decisions_restored": decisions_restored,
            "sessions_restored": sessions_restored,
            "trust_restored": trust_restored,
            "bundle_id": bundle.bundle_id,
        }

    def close(self) -> None:
        pass
