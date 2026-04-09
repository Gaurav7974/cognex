"""
Substrate Context - Manages singleton instances of all substrate components.
"""

import os
import threading
from pathlib import Path
from typing import Optional

from substrate import (
    CognitiveSubstrate,
    TrustGradientEngine,
    DecisionLedger,
    TeleportProtocol,
    IntentCompiler,
)
from substrate.units import CognitiveUnitStore


class SubstrateContext:
    """Manages singleton instances of all substrate components.

    Provides thread-safe access to:
    - CognitiveSubstrate (memory)
    - TrustGradientEngine (trust)
    - DecisionLedger (decisions)
    - TeleportProtocol (teleport)
    - IntentCompiler (swarm)
    """

    _instance: Optional["SubstrateContext"] = None
    _lock = threading.Lock()

    def __init__(self, db_path: Optional[str] = None, project: str = "default"):
        self._db_path = db_path
        self._project = project
        self._substrate: Optional[CognitiveSubstrate] = None
        self._trust: Optional[TrustGradientEngine] = None
        self._ledger: Optional[DecisionLedger] = None
        self._teleport: Optional[TeleportProtocol] = None
        self._swarm: Optional[IntentCompiler] = None
        self._unit_store: Optional[CognitiveUnitStore] = None
        self._initialized = False

    @classmethod
    def get_instance(
        cls, db_path: Optional[str] = None, project: str = "default"
    ) -> "SubstrateContext":
        """Get or create the singleton SubstrateContext instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(db_path=db_path, project=project)
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton (useful for testing)."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.close()
            cls._instance = None

    def _ensure_initialized(self) -> None:
        """Lazy initialization of all substrate components."""
        if self._initialized:
            return

        # Determine DB path
        if self._db_path:
            db_path = Path(self._db_path)
        else:
            # Default: .substrate/ in current working directory
            db_path = Path.cwd() / ".substrate"

        # Auto-create directory
        db_path.mkdir(parents=True, exist_ok=True)
        db_file = db_path / "substrate.db"

        # Initialize components with shared database
        self._substrate = CognitiveSubstrate(db_path=str(db_file))
        self._trust = TrustGradientEngine(db_path=str(db_file))
        self._ledger = DecisionLedger(db_path=str(db_file))
        self._teleport = TeleportProtocol()  # No db_path param
        self._swarm = IntentCompiler()
        self._unit_store = CognitiveUnitStore(db_path=str(db_file))

        self._initialized = True

    @property
    def substrate(self) -> CognitiveSubstrate:
        """Get the CognitiveSubstrate instance."""
        self._ensure_initialized()
        return self._substrate

    @property
    def trust(self) -> TrustGradientEngine:
        """Get the TrustGradientEngine instance."""
        self._ensure_initialized()
        return self._trust

    @property
    def ledger(self) -> DecisionLedger:
        """Get the DecisionLedger instance."""
        self._ensure_initialized()
        return self._ledger

    @property
    def teleport(self) -> TeleportProtocol:
        """Get the TeleportProtocol instance."""
        self._ensure_initialized()
        return self._teleport

    @property
    def swarm(self) -> IntentCompiler:
        self._ensure_initialized()
        return self._swarm

    @property
    def unit_store(self) -> CognitiveUnitStore:
        """Get the CognitiveUnitStore instance."""
        self._ensure_initialized()
        return self._unit_store

    @property
    def db_path(self) -> str:
        """Get the database path."""
        return self._db_path or str(Path.cwd() / ".substrate")

    def close(self) -> None:
        """Close all component resources."""
        if self._substrate:
            # CognitiveSubstrate doesn't have a close method
            # Just clear references
            self._substrate = None
        if self._trust:
            self._trust.close()
            self._trust = None
        if self._ledger:
            self._ledger.close()
            self._ledger = None
        # TeleportProtocol has no close method
        self._teleport = None
        # IntentCompiler has no close method
        self._swarm = None
        if self._unit_store:
            self._unit_store.close()
            self._unit_store = None

        self._initialized = False
