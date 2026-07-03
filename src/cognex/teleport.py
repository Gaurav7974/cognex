
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("teleport")

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.serialization import load_ssh_public_key

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

from .chp import ChannelProtocol


def _get_key_dir() -> Path:
    key_dir = Path.home() / ".cognex.db" / "keys"
    key_dir.mkdir(parents=True, exist_ok=True)
    return key_dir


def _get_key_path() -> Path:
    return _get_key_dir() / "signing_key.pem"


def _get_public_key_path() -> Path:
    return _get_key_dir() / "signing_key.pub"


def generate_keypair() -> tuple[bytes, bytes]:
    if not CRYPTO_AVAILABLE:
        raise RuntimeError(
            "cryptography library not installed. Run: pip install cryptography"
        )

    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_raw = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )

    public_ssh = public_key.public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH,
    )

    return private_raw, public_ssh


def get_or_create_keys() -> tuple[bytes, bytes]:
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
        if not pub_path.exists():
            pub_path.write_bytes(public_pem)
            try:
                pub_path.chmod(0o644)
            except Exception:
                pass
        return private_bytes, public_pem

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
    import hashlib
    return hashlib.sha256(public_key_pem).hexdigest()[:16]


def export_public_key() -> str:
    _, public_pem = get_or_create_keys()
    import base64
    return base64.b64encode(public_pem).decode()


def rotate_keys() -> tuple[bytes, bytes]:
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
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("cryptography library not installed")

    private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key_pem)
    return private_key.sign(content.encode())


def verify_signature(content: str, signature: bytes, public_key_pem: bytes) -> bool:
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
    bundle: StateBundle, public_key_pem: Optional[bytes] = None
) -> bool:
    return bundle.verify(public_key_pem)


@dataclass(frozen=True)
class StateBundle:

    bundle_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    version: str = "2.0"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_host: str = ""
    target_host: str = ""

    session_id: str = ""
    project: str = ""
    session_summary: str = ""

    memories: tuple[dict, ...] = ()

    memory_ids: tuple[str, ...] = ()

    trust_records: tuple[dict, ...] = ()

    decisions: tuple[dict, ...] = ()

    decision_ids: tuple[str, ...] = ()

    workspace_context: str = ""
    pending_tasks: tuple[str, ...] = ()
    last_action: str = ""

    model_name:  str            = ""
    tool_claims: tuple[str, ...] = ()
    signature:   str            = ""
    key_fingerprint: str        = ""

    cognitive_units: tuple[dict, ...] = ()
    state_projections: tuple[dict, ...] = ()

    def serialize(self) -> str:
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
                "memories": list(self.memories),
                "decisions": list(self.decisions),
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
                "cognitive_units":   list(self.cognitive_units),
            },
            indent=2,
        )

    @classmethod
    def deserialize(cls, data: str) -> StateBundle:
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
            memories=tuple(d.get("memories", [])),
            decisions=tuple(d.get("decisions", [])),
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
            cognitive_units=tuple(d.get("cognitive_units", [])),
        )

    def _canonical_payload(self) -> str:
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

    def sign(self) -> StateBundle:
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

    def _copy_with_signature(self, signature: str, key_fingerprint: str = "") -> StateBundle:
        return StateBundle(
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
            cognitive_units=self.cognitive_units,
            state_projections=self.state_projections,
        )

    def verify(self, public_key_pem: Optional[bytes] = None) -> bool:
        if not self.signature:
            return False

        if len(self.signature) == 128 and CRYPTO_AVAILABLE:
            try:
                if public_key_pem is None:
                    _, public_pem = get_or_create_keys()
                    public_key_pem = public_pem
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
    def load_from_file(cls, path: str | Path) -> StateBundle:
        return cls.deserialize(Path(path).read_text())


class StateTransfer:

    def create_bundle(
        self,
        engine,  # CognexEngine
        source_host: str = "",
        target_host: str = "",
        pending_tasks: tuple[str, ...] = (),
        last_action: str = "",
        model_name: str = "",
        tool_claims: tuple[str, ...] = (),
        trust_engine=None,  # Optional TrustEngine
        decision_ledger=None,  # Optional DecisionLedger
        unit_store=None,  # Optional StateUnitStore
    ) -> StateBundle:
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

        trust_records = ()
        if trust_engine is not None:
            trust_summary = trust_engine.get_trust_summary()
            trust_records = tuple(r.as_dict() for r in trust_summary)

        cognitive_units = ()
        state_projections = ()
        if unit_store is not None:
            project = engine.current_project or ""
            units = unit_store.get_bundle(project, scope=None)
            cognitive_units = tuple(u.as_dict() for u in units)

            chp = ChannelProtocol()
            state_projections = tuple(chp.generate_state_view(u) for u in units)

        session_id = engine.current_session or ""
        project = engine.current_project or ""

        bundle = StateBundle(
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
            state_projections=state_projections,
        )
        return bundle.sign()

    def rehydrate(
        self,
        bundle: StateBundle,
        engine,
        trust_engine=None,
        decision_ledger=None,
        unit_store=None,
    ) -> dict:
        if not bundle.verify():
            return {"status": "failed", "reason": "Bundle signature invalid"}

        memories_restored = 0
        sessions_restored = 0
        trust_restored = False
        decisions_restored = 0

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

        if bundle.trust_records and trust_engine is not None:
            from cognex.trust import TrustRecord

            trust_count = 0
            rejected = 0
            for tr in bundle.trust_records:
                try:
                    record = TrustRecord.from_dict(tr)

                    approval_count = getattr(record, "approval_count", 0)
                    violation_count = getattr(record, "violation_count", 0)
                    if approval_count > 500 or violation_count > 100:
                        rejected += 1
                        continue

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

        units_restored = 0
        if bundle.cognitive_units and unit_store is not None:
            from cognex.models import StateUnit

            for cu_dict in bundle.cognitive_units:
                try:
                    unit = StateUnit.from_dict(cu_dict)
                    unit_store.save(unit)
                    units_restored += 1
                except Exception:
                    pass


        projections_validated = 0
        if bundle.state_projections:
            chp = ChannelProtocol()
            for projection in bundle.state_projections:
                if "unit_id" in projection:
                    projections_validated += 1

        return {
            "status": "success",
            "bundle_version": bundle.version,
            "memories_restored": memories_restored,
            "decisions_restored": decisions_restored,
            "sessions_restored": sessions_restored,
            "trust_restored": trust_restored,
            "units_restored": units_restored,
            "chp_projections_validated": projections_validated,
            "bundle_id": bundle.bundle_id,
        }

