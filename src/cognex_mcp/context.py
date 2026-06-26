"""Cognex Context — manages singleton instances of all cognex components.

Lifecycle
---------
The previous implementation had a race window between the ``_initialized``
flag check and the actual component construction.  Two threads arriving
simultaneously could both see ``_initialized = False`` and race to construct
duplicate instances, leaving one set orphaned with open database connections.

This version uses an explicit per-instance ``_init_lock`` threading.Lock so
that only one thread can execute ``_ensure_initialized()`` at a time.  All
subsequent threads block until initialisation is complete, then proceed with
the guarantee that ``_initialized = True`` and all components are ready.

Additionally, ``startup()`` is provided as an explicit, eager initialisation
path.  The MCP server's ``lifespan`` handler should call ``startup()`` before
accepting any tool requests, so that the first real request is never delayed
by database I/O and migration execution.
"""

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
    TrustGradientEngine,
    DecisionLedger,
    TeleportProtocol,
    IntentCompiler,
    CHPProtocol,
)
from cognex.audit import AuditLog
from cognex.units import CognitiveUnitStore

logger = logging.getLogger("cognex-context")


# ---------------------------------------------------------------------------
# SQLite capability probe
# ---------------------------------------------------------------------------

def check_fts5_available() -> bool:
    """Return True if this SQLite build has FTS5 compiled in."""
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


# ---------------------------------------------------------------------------
# CognexContext
# ---------------------------------------------------------------------------

class CognexContext:
    """Thread-safe singleton manager for all cognex components.

    Provides shared access to:
    - ``engine``      — CognexEngine (memory store + session tracking)
    - ``trust``       — TrustGradientEngine (permission learning)
    - ``ledger``      — DecisionLedger (decision history)
    - ``teleport``    — TeleportProtocol (bundle import/export)
    - ``swarm``       — IntentCompiler (multi-agent coordination)
    - ``unit_store``  — CognitiveUnitStore (long-lived cognitive units)
    - ``audit``       — AuditLog (tamper-evident event log)
    - ``chp``         — CHPProtocol (cross-session handoff state)
    """

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
        self._trust: Optional[TrustGradientEngine] = None
        self._ledger: Optional[DecisionLedger] = None
        self._teleport: Optional[TeleportProtocol] = None
        self._swarm: Optional[IntentCompiler] = None
        self._unit_store: Optional[CognitiveUnitStore] = None
        self._audit: Optional[AuditLog] = None
        self._chp: Optional[CHPProtocol] = None
        self._initialized = False

        # Guards _ensure_initialized() from concurrent double-init.
        self._init_lock = threading.Lock()

        # Startup metadata for health reporting.
        self._startup_at: Optional[datetime] = None
        self._db_file: Optional[Path] = None

    # ── Singleton factory ─────────────────────────────────────────────────

    @classmethod
    def get_instance(
        cls,
        db_path: Optional[str] = None,
        project: str = "default",
        pool_size: int | None = None,
    ) -> "CognexContext":
        """Return the singleton instance, creating it if necessary."""
        with cls._class_lock:
            if cls._instance is None:
                cls._instance = cls(
                    db_path=db_path, project=project, pool_size=pool_size
                )
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Destroy the singleton.  Required in tests to prevent state leakage."""
        with cls._class_lock:
            if cls._instance is not None:
                cls._instance.close()
            cls._instance = None

    # ── Explicit startup ──────────────────────────────────────────────────

    def startup(self) -> None:
        """Eagerly initialise all components.

        Call this from the MCP server's lifespan handler so that the first
        tool request is not delayed by database I/O and migration execution.
        """
        self._ensure_initialized()
        logger.info(
            "Cognex engine started (db=%s, project=%s, migrations=complete)",
            self._db_file,
            self._project,
        )

    # ── Lazy initialisation ───────────────────────────────────────────────

    def _ensure_initialized(self) -> None:
        """Initialise all components exactly once, regardless of thread count.

        The double-checked locking pattern here is correct in CPython because
        reading ``self._initialized`` under the GIL gives a consistent view.
        The lock is only taken when initialisation is actually required, and
        the flag is set *after* all components are fully constructed so that
        no thread can observe a partial state.
        """
        if self._initialized:
            return

        with self._init_lock:
            # Re-check inside the lock (second check in double-checked locking).
            if self._initialized:
                return

            self._do_init()

    def _do_init(self) -> None:
        """Construct all components.  Called with self._init_lock held."""
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
        self._trust      = TrustGradientEngine(db_path=str(db_file))
        self._ledger     = DecisionLedger(db_path=str(db_file))
        self._teleport   = TeleportProtocol()      # stateless, no db_path
        self._swarm      = IntentCompiler()
        self._unit_store = CognitiveUnitStore(db_path=str(db_file))
        self._audit      = AuditLog(db_path=str(db_file))
        self._chp        = CHPProtocol()           # in-memory shared state

        self._startup_at  = datetime.now(timezone.utc)
        self._initialized = True                   # Set last — visible to other threads.

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def engine(self) -> CognexEngine:
        self._ensure_initialized()
        assert self._engine is not None
        return self._engine

    @property
    def trust(self) -> TrustGradientEngine:
        self._ensure_initialized()
        assert self._trust is not None
        return self._trust

    @property
    def ledger(self) -> DecisionLedger:
        self._ensure_initialized()
        assert self._ledger is not None
        return self._ledger

    @property
    def teleport(self) -> TeleportProtocol:
        self._ensure_initialized()
        assert self._teleport is not None
        return self._teleport

    @property
    def swarm(self) -> IntentCompiler:
        self._ensure_initialized()
        assert self._swarm is not None
        return self._swarm

    @property
    def unit_store(self) -> CognitiveUnitStore:
        self._ensure_initialized()
        assert self._unit_store is not None
        return self._unit_store

    @property
    def audit(self) -> AuditLog:
        self._ensure_initialized()
        assert self._audit is not None
        return self._audit

    @property
    def chp(self) -> CHPProtocol:
        """Shared CHPProtocol instance.

        Must be shared rather than constructed per-call — CHP holds in-memory
        entanglement state that must persist across tool calls for a handoff
        to complete.  A fresh instance created per request would lose all
        pending handoffs.
        """
        self._ensure_initialized()
        assert self._chp is not None
        return self._chp

    @property
    def db_path(self) -> str:
        """The resolved database file path (used for health reporting)."""
        if self._db_file:
            return str(self._db_file)
        return self._db_path or str(Path.home() / ".cognex.db" / "cognex.db")

    # ── Health ────────────────────────────────────────────────────────────

    def health_check(self) -> dict:
        """Return a dict describing the current health of all components.

        Used by the ``cognex_health`` MCP tool.

        Returns:
            Dict with keys:
            - ``status``           — ``"ok"`` or ``"degraded"``
            - ``initialized``      — bool
            - ``db_path``          — str
            - ``db_reachable``     — bool (can execute a simple query)
            - ``fts5_available``   — bool
            - ``memory_count``     — int | None
            - ``startup_at``       — ISO-8601 str | None
            - ``uptime_seconds``   — float | None
            - ``components``       — dict mapping component name → "ok"/"missing"
        """
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

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def close(self) -> None:
        """Close all component resources and release database connections."""
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

        self._initialized = False
