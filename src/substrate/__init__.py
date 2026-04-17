"""
Cognitive Substrate — Persistent Memory for AI Agents

An AI that remembers you. The foundation everything else sits on.
"""

try:
    from importlib.metadata import version

    __version__ = version("cognex")
except Exception:
    __version__ = "0.0.0+unknown"

from .models import MemoryEntry, MemoryType, MemoryScope, SessionSnapshot
from .store import MemoryStore
from .extractor import MemoryExtractor, ExtractionResult
from .retriever import MemoryRetriever
from .substrate import CognitiveSubstrate, SubstrateReport
from .trust import TrustGradientEngine, TrustRecord, TrustLevel, PermissionDecision
from .ledger import DecisionLedger, DecisionEntry
from .teleport import TeleportProtocol, TeleportBundle
from .swarm import IntentCompiler, SwarmPlan, SubTask, AgentRole, TaskStatus
from .patterns import PatternAnalyzer, PatternInsight
from .chp import CHPProtocol

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
    "CognitiveSubstrate",
    "SubstrateReport",
    "TrustGradientEngine",
    "TrustRecord",
    "TrustLevel",
    "PermissionDecision",
    "DecisionLedger",
    "DecisionEntry",
    "TeleportProtocol",
    "TeleportBundle",
    "IntentCompiler",
    "SwarmPlan",
    "SubTask",
    "AgentRole",
    "TaskStatus",
    "PatternAnalyzer",
    "PatternInsight",
    "CHPProtocol",
]
