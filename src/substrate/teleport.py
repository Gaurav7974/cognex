"""Teleport Protocol — serialize, transfer, and rehydrate agent state."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("teleport")

# Try to import cryptography for Ed25519 signing
try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.backends import default_backend

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


# Key file location
def _get_key_path() -> Path:
    """Get path to signing key."""
    key_dir = Path(".substrate")
    key_dir.mkdir(parents=True, exist_ok=True)
    return key_dir / "signing_key.pem"


def generate_keypair() -> tuple[bytes, bytes]:
    """Generate Ed25519 keypair. Returns (private_key_raw_32bytes, public_key_ssh)."""
    if not CRYPTO_AVAILABLE:
        raise RuntimeError(
            "cryptography library not installed. Run: pip install cryptography"
        )

    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    # Private key as raw 32 bytes
    private_raw = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Public key as OpenSSH format for easy verification
    public_ssh = public_key.public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH,
    )

    return private_raw, public_ssh


def get_or_create_keys() -> tuple[bytes, bytes]:
    """Get existing keys or generate new ones."""
    key_path = _get_key_path()

    if key_path.exists():
        private_bytes = key_path.read_bytes()
        # Must be raw 32 bytes
        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_bytes)
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH,
        )
        return private_bytes, public_pem

    # Generate new keypair
    private_raw, public_pem = generate_keypair()
    key_path.write_bytes(private_raw)
    # Secure the key file
    try:
        key_path.chmod(0o600)
    except Exception:
        pass
    return private_raw, public_pem

    # Generate new keypair
    private_pem, public_pem = generate_keypair()
    # Save as raw 32 bytes for easier loading
    private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_pem)
    private_raw = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    key_path.write_bytes(private_raw)
    # Secure the key file
    try:
        key_path.chmod(0o600)
    except Exception:
        pass
    return private_raw, public_pem


def sign_bundle(content: str, private_key_pem: bytes) -> bytes:
    """Sign bundle content with Ed25519."""
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("cryptography library not installed")

    private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key_pem)
    return private_key.sign(content.encode())


def verify_signature(content: str, signature: bytes, public_key_pem: bytes) -> bool:
    """Verify Ed25519 signature."""
    if not CRYPTO_AVAILABLE:
        return False

    try:
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_key_pem)
        public_key.verify(signature, content.encode())
        return True
    except Exception:
        return False


def verify_bundle(
    bundle: TeleportBundle, public_key_pem: Optional[bytes] = None
) -> bool:
    """Verify a teleport bundle's integrity.

    Args:
        bundle: The TeleportBundle to verify
        public_key_pem: Optional public key (if None, loads from default location)

    Returns:
        True if signature is valid, False otherwise
    """
    return bundle.verify(public_key_pem)


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

    # Cognitive Units (v3.0) - for CHP handoff protocol
    cognitive_units: tuple[dict, ...] = ()  # Serialized CognitiveUnit objects

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
                # v3.0: Cognitive Units
                "cognitive_units": list(self.cognitive_units),
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
            # v3.0: Cognitive Units
            cognitive_units=tuple(d.get("cognitive_units", [])),
        )

    def _canonical_payload(self) -> str:
        """Create canonical string for signing (excludes signature field)."""
        return (
            f"{self.bundle_id}:{self.version}:{self.created_at.isoformat()}:"
            f"{self.source_host}:{self.target_host}:{self.session_id}:"
            f"{self.project}:{self.session_summary}:"
            f"{len(self.memories)}:{self.memories!r}:"
            f"{len(self.decisions)}:{self.decisions!r}:"
            f"{len(self.trust_records)}:{self.trust_records!r}:"
            f"{self.workspace_context}:{self.pending_tasks!r}:"
            f"{self.last_action}:{self.model_name}:{self.tool_claims!r}"
        )

    def sign(self) -> TeleportBundle:
        """Sign the bundle with Ed25519."""
        if not CRYPTO_AVAILABLE:
            # Fallback to hash-based (not secure, for dev only)
            import hashlib

            payload = self._canonical_payload()
            sig = hashlib.sha256(payload.encode()).hexdigest()[:16]
            return self._copy_with_signature(sig)

        try:
            private_pem, _ = get_or_create_keys()
            payload = self._canonical_payload()
            sig = sign_bundle(payload, private_pem)
            # Ed25519 signature is 64 bytes = 128 hex chars
            return self._copy_with_signature(sig.hex())
        except Exception as e:
            # Fallback on error
            import hashlib

            payload = self._canonical_payload()
            sig = hashlib.sha256(payload.encode()).hexdigest()[:16]
            return self._copy_with_signature(sig)

    def _copy_with_signature(self, signature: str) -> TeleportBundle:
        """Create copy with signature set."""
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
            signature=signature,
        )

    def verify(self, public_key_pem: Optional[bytes] = None) -> bool:
        """Verify the bundle hasn't been tampered with."""
        if not self.signature:
            return False

        # Check if Ed25519 signature (hex-encoded, 64 bytes = 128 hex chars)
        if len(self.signature) == 128 and CRYPTO_AVAILABLE:
            try:
                if public_key_pem is None:
                    _, public_pem = get_or_create_keys()
                    public_key_pem = public_pem
                payload = self._canonical_payload()
                sig_bytes = bytes.fromhex(self.signature)
                return verify_signature(payload, sig_bytes, public_key_pem)
            except Exception:
                return False

        # Fallback: check if old SHA256 signature matches (16 hex chars)
        if len(self.signature) == 16:
            import hashlib

            payload = self._canonical_payload()
            expected = hashlib.sha256(payload.encode()).hexdigest()[:16]
            return self.signature == expected

        return False

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
        unit_store=None,  # Optional CognitiveUnitStore
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

        # v3.0: Gather cognitive units for CHP handoff
        cognitive_units = ()
        if unit_store is not None:
            project = substrate.current_project or ""
            units = unit_store.get_bundle(project, scope=None)
            cognitive_units = tuple(u.as_dict() for u in units)

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
            cognitive_units=cognitive_units,
        )
        return bundle.sign()

    def rehydrate(
        self,
        bundle: TeleportBundle,
        substrate,
        trust_engine=None,
        decision_ledger=None,
        unit_store=None,
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
            rejected = 0
            for tr in bundle.trust_records:
                try:
                    # Restore the full TrustRecord from serialized dict
                    record = TrustRecord.from_dict(tr)

                    # Security cap: reject malicious injection attempts
                    approval_count = getattr(record, "approval_count", 0)
                    violation_count = getattr(record, "violation_count", 0)
                    if approval_count > 500 or violation_count > 100:
                        rejected += 1
                        continue

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

            if rejected > 0:
                logger.warning(
                    f"Rejected {rejected} trust records due to suspicious counts"
                )

        # v3.0: Restore cognitive units for CHP handoff
        cognitive_units_restored = 0
        if bundle.cognitive_units and unit_store is not None:
            from substrate.models import CognitiveUnit

            for cu_dict in bundle.cognitive_units:
                try:
                    unit = CognitiveUnit.from_dict(cu_dict)
                    unit_store.save(unit)
                    cognitive_units_restored += 1
                except Exception:
                    pass

        return {
            "status": "success",
            "bundle_version": bundle.version,
            "memories_restored": memories_restored,
            "decisions_restored": decisions_restored,
            "sessions_restored": sessions_restored,
            "trust_restored": trust_restored,
            "cognitive_units_restored": cognitive_units_restored,
            "bundle_id": bundle.bundle_id,
        }

    def close(self) -> None:
        pass
