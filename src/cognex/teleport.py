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
    from cryptography.hazmat.primitives.serialization import load_ssh_public_key

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

from .chp import CHPProtocol


# Key file location — stored in the user's home directory so keys persist
# across projects and are not accidentally committed to source control.
def _get_key_dir() -> Path:
    """Return the directory that holds Ed25519 signing keys."""
    key_dir = Path.home() / ".cognex.db" / "keys"
    key_dir.mkdir(parents=True, exist_ok=True)
    return key_dir


def _get_key_path() -> Path:
    """Return path to the private signing key (raw 32-byte Ed25519)."""
    return _get_key_dir() / "signing_key.pem"


def _get_public_key_path() -> Path:
    """Return path to the corresponding public key (OpenSSH format)."""
    return _get_key_dir() / "signing_key.pub"


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
    """Get existing keys or generate new ones.

    On first call, generates a fresh Ed25519 keypair, writes the private
    key to ``~/.cognex.db/keys/signing_key.pem`` (mode 0o600) and the public
    key to ``signing_key.pub`` (mode 0o644).

    Returns:
        (private_key_raw_32bytes, public_key_ssh_bytes)
    """
    key_path = _get_key_path()
    pub_path = _get_public_key_path()

    if key_path.exists():
        private_bytes = key_path.read_bytes()
        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_bytes)
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH,
        )
        # Write public key if it was lost (e.g., manual deletion).
        if not pub_path.exists():
            pub_path.write_bytes(public_pem)
            try:
                pub_path.chmod(0o644)
            except Exception:
                pass
        return private_bytes, public_pem

    # Generate new keypair.
    private_raw, public_pem = generate_keypair()
    key_path.write_bytes(private_raw)
    pub_path.write_bytes(public_pem)
    try:
        key_path.chmod(0o600)
        pub_path.chmod(0o644)
    except Exception:
        pass
    return private_raw, public_pem


def get_key_fingerprint(public_key_pem: bytes) -> str:
    """Return a short (16 hex char) stable fingerprint of a public key.

    Embedded in TeleportBundles so that a receiving machine can warn
    when the bundle was signed with a different key than its local key.
    """
    import hashlib
    return hashlib.sha256(public_key_pem).hexdigest()[:16]


def export_public_key() -> str:
    """Return the local public key as a base64 string for easy sharing."""
    _, public_pem = get_or_create_keys()
    import base64
    return base64.b64encode(public_pem).decode()


def rotate_keys() -> tuple[bytes, bytes]:
    """Generate a new keypair, archiving the old private key.

    The old private key is renamed to
    ``signing_key.pem.bak.<timestamp>`` before the new key is written.

    Returns:
        (new_private_key_raw, new_public_key_pem)
    """
    key_path = _get_key_path()
    if key_path.exists():
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = key_path.parent / f"signing_key.pem.bak.{ts}"
        key_path.rename(backup)
        try:
            backup.chmod(0o600)
        except Exception:
            pass

    private_raw, public_pem = generate_keypair()
    pub_path = _get_public_key_path()
    key_path.write_bytes(private_raw)
    pub_path.write_bytes(public_pem)
    try:
        key_path.chmod(0o600)
        pub_path.chmod(0o644)
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
        # Public key is stored/exported as OpenSSH format bytes.
        public_key = load_ssh_public_key(public_key_pem, backend=default_backend())
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
    model_name:  str            = ""
    tool_claims: tuple[str, ...] = ()
    signature:   str            = ""  # Ed25519 hex or sha256 fallback
    key_fingerprint: str        = ""  # Fingerprint of signing key for cross-machine validation

    # Cognitive Units (v3.0) — for CHP handoff protocol
    cognitive_units: tuple[dict, ...] = ()
    chp_projections: tuple[dict, ...] = ()

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
                "tool_claims":       list(self.tool_claims),
                "signature":         self.signature,
                "key_fingerprint":   self.key_fingerprint,
                # v3.0: Cognitive Units
                "cognitive_units":   list(self.cognitive_units),
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
            key_fingerprint=d.get("key_fingerprint", ""),
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
        """Sign the bundle with Ed25519, embedding the key fingerprint."""
        if not CRYPTO_AVAILABLE:
            import hashlib
            payload = self._canonical_payload()
            sig = hashlib.sha256(payload.encode()).hexdigest()[:16]
            return self._copy_with_signature(sig, "")

        try:
            private_pem, public_pem = get_or_create_keys()
            payload = self._canonical_payload()
            sig = sign_bundle(payload, private_pem)
            fingerprint = get_key_fingerprint(public_pem)
            return self._copy_with_signature(sig.hex(), fingerprint)
        except Exception:
            import hashlib
            payload = self._canonical_payload()
            sig = hashlib.sha256(payload.encode()).hexdigest()[:16]
            return self._copy_with_signature(sig, "")

    def _copy_with_signature(self, signature: str, key_fingerprint: str = "") -> TeleportBundle:
        """Create a copy with signature and key_fingerprint set."""
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
            key_fingerprint=key_fingerprint,
        )

    def verify(self, public_key_pem: Optional[bytes] = None) -> bool:
        """Verify the bundle hasn't been tampered with."""
        if not self.signature:
            return False

        # Ed25519 signature (128 hex chars)
        if len(self.signature) == 128 and CRYPTO_AVAILABLE:
            try:
                if public_key_pem is None:
                    _, public_pem = get_or_create_keys()
                    public_key_pem = public_pem
                # Warn if fingerprints mismatch (key rotation, cross-machine).
                if self.key_fingerprint:
                    local_fp = get_key_fingerprint(public_key_pem)
                    if local_fp != self.key_fingerprint:
                        import logging
                        logging.getLogger("teleport").warning(
                            "Bundle key fingerprint %s differs from local key %s — "
                            "bundle was signed on a different machine or key was rotated.",
                            self.key_fingerprint, local_fp,
                        )
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
            engine=engine,
            source_host="laptop",
            target_host="production-server",
        )
        # Save and transfer (in real use, send over network)
        bundle.save_to_file("teleport.json")
        # On target machine:
        received = TeleportBundle.load_from_file("teleport.json")
        if received.verify():
            state = protocol.rehydrate(received, engine)
    """

    def create_bundle(
        self,
        engine,  # CognexEngine
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
        """Create a teleport bundle from an engine's current state.

        Args:
            engine: The CognexEngine instance
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
        all_memories = engine.store.search(limit=9999)
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
        chp_projections = ()
        if unit_store is not None:
            project = engine.current_project or ""
            units = unit_store.get_bundle(project, scope=None)
            cognitive_units = tuple(u.as_dict() for u in units)

            # CHP Enhancement: Create holographic projections for advanced handoff
            chp = CHPProtocol()
            chp_projections = tuple(chp.holographic_project(u) for u in units)

        # Gather session info
        session_id = engine.current_session or ""
        project = engine.current_project or ""

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
            chp_projections=chp_projections,
        )
        return bundle.sign()

    def rehydrate(
        self,
        bundle: TeleportBundle,
        engine,
        trust_engine=None,
        decision_ledger=None,
        unit_store=None,
    ) -> dict:
        """Rehydrate an engine from a teleport bundle.

        Args:
            bundle: The TeleportBundle to restore from
            engine: The CognexEngine instance
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
                engine.start_session(bundle.session_id, project=bundle.project)
                sessions_restored = 1
            except Exception:
                pass

        # v2.0: Restore full memory content (cross-machine compatible).
        # Uses save_many_bulk() to rebuild FTS5 index once at end instead
        # of triggering N per-row FTS inserts (major speedup for large bundles).
        if bundle.memories and hasattr(engine, "store"):
            from cognex.models import MemoryEntry

            restored_memories = []
            for mem_dict in bundle.memories:
                try:
                    memory = MemoryEntry.from_dict(mem_dict)
                    restored_memories.append(memory)
                except Exception:
                    pass

            if restored_memories:
                memories_restored = engine.store.save_many_bulk(restored_memories)

        # v2.0: Restore full decision content (cross-machine compatible)
        if bundle.decisions and decision_ledger is not None:
            from cognex.ledger import DecisionEntry

            for dec_dict in bundle.decisions:
                try:
                    decision = DecisionEntry.from_dict(dec_dict)
                    decision_ledger._save(decision)
                    decisions_restored += 1
                except Exception:
                    pass

        # Restore trust records using the provided trust engine
        if bundle.trust_records and trust_engine is not None:
            from cognex.trust import TrustRecord

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
            from cognex.models import CognitiveUnit

            for cu_dict in bundle.cognitive_units:
                try:
                    unit = CognitiveUnit.from_dict(cu_dict)
                    unit_store.save(unit)
                    cognitive_units_restored += 1
                except Exception:
                    pass

        # CHP Enhancement: Process holographic projections for advanced handoff validation
        chp_validated = 0
        if bundle.chp_projections:
            chp = CHPProtocol()
            for projection in bundle.chp_projections:
                # Validate projection integrity (simplified for demo)
                if "unit_id" in projection:
                    chp_validated += 1

        return {
            "status": "success",
            "bundle_version": bundle.version,
            "memories_restored": memories_restored,
            "decisions_restored": decisions_restored,
            "sessions_restored": sessions_restored,
            "trust_restored": trust_restored,
            "cognitive_units_restored": cognitive_units_restored,
            "chp_projections_validated": chp_validated,
            "bundle_id": bundle.bundle_id,
        }

    def close(self) -> None:
        pass
