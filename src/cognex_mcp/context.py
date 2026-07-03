
from __future__ import annotations

import logging
import os
import sqlite3
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from cognex import (
    CognexEngine,
    TrustEngine,
    DecisionLedger,
    StateTransfer,
    TaskPlanner,
    ChannelProtocol,
)
from cognex.audit import AuditLog
from cognex.handoff import HandoffStore
from cognex.integrity import IntegrityStore
from cognex.provenance import ProvenanceStore
from cognex.reconcile import Reconciler
from cognex.units import StateUnitStore

logger = logging.getLogger("cognex-context")


# SQLite capability probe

def check_fts5_available() -> bool:
    conn = sqlite3.connect(":memory:")
    try:
        result = conn.execute(
            "SELECT * FROM pragma_compile_options "
            "WHERE compile_options LIKE 'ENABLE_FTS5'"
        ).fetchone()
        return result is not None
    except Exception:
        return False
    finally:
        conn.close()


# CognexContext

class CognexContext:

    _instance: Optional["CognexContext"] = None
    _class_lock = threading.Lock()  # Guards _instance creation only.

    def __init__(
        self,
        db_path: Optional[str] = None,
        project: str = "default",
        pool_size: int | None = None,
    ) -> None:
        self._db_path = db_path
        self._project = project
        self._pool_size = pool_size

        # Components — None until _ensure_initialized() is called.
        self._engine: Optional[CognexEngine] = None
        self._trust: Optional[TrustEngine] = None
        self._ledger: Optional[DecisionLedger] = None
        self._teleport: Optional[StateTransfer] = None
        self._swarm: Optional[TaskPlanner] = None
        self._unit_store: Optional[StateUnitStore] = None
        self._audit: Optional[AuditLog] = None
        self._chp: Optional[ChannelProtocol] = None
        self._provenance: Optional[ProvenanceStore] = None
        self._integrity: Optional[IntegrityStore] = None
        self._handoff: Optional[HandoffStore] = None
        self._reconciler: Optional[Reconciler] = None
        self._initialized = False

        # Guards _ensure_initialized() from concurrent double-init.
        self._init_lock = threading.Lock()

        # Startup metadata for health reporting.
        self._startup_at: Optional[datetime] = None
        self._db_file: Optional[Path] = None


    @classmethod
    def get_instance(
        cls,
        db_path: Optional[str] = None,
        project: str = "default",
        pool_size: int | None = None,
    ) -> "CognexContext":
        with cls._class_lock:
            if cls._instance is None:
                cls._instance = cls(
                    db_path=db_path, project=project, pool_size=pool_size
                )
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._class_lock:
            if cls._instance is not None:
                cls._instance.close()
            cls._instance = None


    def startup(self) -> None:
        self._ensure_initialized()
        logger.info(
            "Cognex engine started (db=%s, project=%s, migrations=complete)",
            self._db_file,
            self._project,
        )


    def _ensure_initialized(self) -> None:
        if self._initialized:
            return

        with self._init_lock:
            # Re-check inside the lock (second check in double-checked locking).
            if self._initialized:
                return

            self._do_init()

    def _do_init(self) -> None:
        if not check_fts5_available():
            logger.warning(
                "FTS5 is not compiled into this SQLite build. "
                "Memory search will fall back to slower LIKE queries. "
                "Rebuild SQLite with --enable-fts5 for better performance."
            )

        # Resolve the database file path.
        if self._db_path:
            configured = Path(self._db_path)
            if configured.suffix:
                db_file = configured
                db_file.parent.mkdir(parents=True, exist_ok=True)
            else:
                configured.mkdir(parents=True, exist_ok=True)
                db_file = configured / "cognex.db"
        else:
            db_dir = Path.home() / ".cognex.db"
            db_dir.mkdir(parents=True, exist_ok=True)
            db_file = db_dir / "cognex.db"

        self._db_file = db_file

        # Construct components.  All share the same on-disk database file.
        self._engine  = CognexEngine(db_path=str(db_file), pool_size=self._pool_size)
        self._trust      = TrustEngine(db_path=str(db_file))
        self._ledger     = DecisionLedger(db_path=str(db_file))
        self._teleport   = StateTransfer()      # stateless, no db_path
        self._swarm      = TaskPlanner()
        self._unit_store = StateUnitStore(db_path=str(db_file))
        self._audit      = AuditLog(db_path=str(db_file))
        self._chp        = ChannelProtocol()           # in-memory shared state
        self._provenance = ProvenanceStore(db_path=str(db_file))
        self._integrity  = IntegrityStore(db_path=str(db_file))
        self._handoff    = HandoffStore(db_path=str(db_file))
        self._reconciler = Reconciler(db_path=str(db_file))

        self._startup_at  = datetime.now(timezone.utc)
        self._initialized = True                   # Set last — visible to other threads.


    @property
    def engine(self) -> CognexEngine:
        self._ensure_initialized()
        assert self._engine is not None
        return self._engine

    @property
    def trust(self) -> TrustEngine:
        self._ensure_initialized()
        assert self._trust is not None
        return self._trust

    @property
    def ledger(self) -> DecisionLedger:
        self._ensure_initialized()
        assert self._ledger is not None
        return self._ledger

    @property
    def teleport(self) -> StateTransfer:
        self._ensure_initialized()
        assert self._teleport is not None
        return self._teleport

    @property
    def swarm(self) -> TaskPlanner:
        self._ensure_initialized()
        assert self._swarm is not None
        return self._swarm

    @property
    def unit_store(self) -> StateUnitStore:
        self._ensure_initialized()
        assert self._unit_store is not None
        return self._unit_store

    @property
    def audit(self) -> AuditLog:
        self._ensure_initialized()
        assert self._audit is not None
        return self._audit

    @property
    def chp(self) -> ChannelProtocol:
        self._ensure_initialized()
        assert self._chp is not None
        return self._chp

    @property
    def provenance(self) -> ProvenanceStore:
        self._ensure_initialized()
        assert self._provenance is not None
        return self._provenance

    @property
    def integrity(self) -> IntegrityStore:
        self._ensure_initialized()
        assert self._integrity is not None
        return self._integrity

    @property
    def handoff(self) -> HandoffStore:
        self._ensure_initialized()
        assert self._handoff is not None
        return self._handoff

    @property
    def reconciler(self) -> Reconciler:
        self._ensure_initialized()
        assert self._reconciler is not None
        return self._reconciler

    @property
    def db_path(self) -> str:
        if self._db_file:
            return str(self._db_file)
        return self._db_path or str(Path.home() / ".cognex.db" / "cognex.db")


    def health_check(self) -> dict:
        db_reachable = False
        memory_count: int | None = None
        components: dict[str, str] = {}

        if self._initialized:
            try:
                memory_count = self._engine.store.count()
                db_reachable = True
            except Exception:
                pass

            for name, obj in [
                ("engine",     self._engine),
                ("trust",      self._trust),
                ("ledger",     self._ledger),
                ("teleport",   self._teleport),
                ("swarm",      self._swarm),
                ("unit_store", self._unit_store),
                ("audit",      self._audit),
                ("chp",        self._chp),
                ("provenance", self._provenance),
                ("integrity",  self._integrity),
                ("handoff",    self._handoff),
                ("reconciler", self._reconciler),
            ]:
                components[name] = "ok" if obj is not None else "missing"

        uptime: float | None = None
        if self._startup_at:
            uptime = (datetime.now(timezone.utc) - self._startup_at).total_seconds()

        status = "ok" if (self._initialized and db_reachable) else "degraded"

        return {
            "status":         status,
            "initialized":    self._initialized,
            "db_path":        self.db_path,
            "db_reachable":   db_reachable,
            "fts5_available": check_fts5_available(),
            "memory_count":   memory_count,
            "startup_at":     self._startup_at.isoformat() if self._startup_at else None,
            "uptime_seconds": uptime,
            "components":     components,
        }


    def close(self) -> None:
        if self._engine:
            try:
                self._engine.store.close()
            except Exception:
                pass
            self._engine = None
        if self._trust:
            self._trust.close()
            self._trust = None
        if self._ledger:
            self._ledger.close()
            self._ledger = None
        self._teleport = None  # Stateless, no cleanup needed.
        self._swarm    = None  # Stateless, no cleanup needed.
        if self._unit_store:
            self._unit_store.close()
            self._unit_store = None
        if self._audit:
            self._audit.close()
            self._audit = None
        self._chp = None       # In-memory only, GC handles it.
        if self._provenance:
            self._provenance.close()
            self._provenance = None
        if self._integrity:
            self._integrity.close()
            self._integrity = None
        if self._handoff:
            self._handoff.close()
            self._handoff = None
        if self._reconciler:
            self._reconciler.close()
            self._reconciler = None

        self._initialized = False
