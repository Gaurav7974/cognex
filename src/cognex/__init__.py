
try:
    from importlib.metadata import version

    __version__ = version("cognex")
except Exception:
    __version__ = "0.0.0+unknown"

from .models import MemoryEntry, MemoryType, MemoryScope, SessionSnapshot
from .store import MemoryStore
from .extractor import MemoryExtractor, ExtractionResult
from .retriever import MemoryRetriever
from .cognex import CognexEngine, CognexReport
from .audit import AuditLog
from .trust import TrustEngine, TrustRecord, TrustLevel, PermissionDecision
from .ledger import DecisionLedger, DecisionEntry
from .teleport import StateTransfer, StateBundle
from .swarm import TaskPlanner, TaskPlan, SubTask, AgentRole, TaskStatus
from .patterns import PatternAnalyzer, PatternInsight
from .chp import ChannelProtocol

__all__ = [
    "__version__",
    "MemoryEntry",
    "MemoryType",
    "MemoryScope",
    "SessionSnapshot",
    "MemoryStore",
    "MemoryExtractor",
    "ExtractionResult",
    "MemoryRetriever",
    "CognexEngine",
    "CognexReport",
    "AuditLog",
    "TrustEngine",
    "TrustRecord",
    "TrustLevel",
    "PermissionDecision",
    "DecisionLedger",
    "DecisionEntry",
    "StateTransfer",
    "StateBundle",
    "TaskPlanner",
    "TaskPlan",
    "SubTask",
    "AgentRole",
    "TaskStatus",
    "PatternAnalyzer",
    "PatternInsight",
    "ChannelProtocol",
]
