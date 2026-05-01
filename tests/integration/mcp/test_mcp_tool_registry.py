import pytest
import sys
from pathlib import Path

src_path = Path(__file__).resolve().parents[3] / "src"
sys.path.insert(0, str(src_path))

from substrate_mcp.tools.registry import TOOL_DEFINITIONS


def test_all_tools_have_required_fields():
    """Verify all tools have name, description, and inputSchema."""
    for tool in TOOL_DEFINITIONS:
        assert "name" in tool, f"Tool missing name: {tool}"
        assert "description" in tool, (
            f"Tool {tool.get('name', '?')} missing description"
        )
        assert "inputSchema" in tool, (
            f"Tool {tool.get('name', '?')} missing inputSchema"
        )


def test_no_duplicate_tool_names():
    """Verify no duplicate tool names exist."""
    names = [t["name"] for t in TOOL_DEFINITIONS]
    assert len(names) == len(set(names)), (
        f"Duplicate tool names found: {[n for n in names if names.count(n) > 1]}"
    )


def test_tool_registry_not_empty():
    """Verify tool registry is populated."""
    assert len(TOOL_DEFINITIONS) > 0, "Tool registry is empty"


def test_core_memory_tools_present():
    """Verify core memory tools are registered."""
    names = [t["name"] for t in TOOL_DEFINITIONS]
    required_core = [
        "memory_add",
        "memory_search",
        "memory_get_context",
        "memory_decay",
    ]
    for name in required_core:
        assert name in names, f"Core memory tool missing from registry: {name}"


def test_core_trust_tools_present():
    """Verify core trust tools are registered."""
    names = [t["name"] for t in TOOL_DEFINITIONS]
    required_trust = [
        "trust_check",
        "trust_record",
    ]
    for name in required_trust:
        assert name in names, f"Core trust tool missing from registry: {name}"


def test_core_ledger_tools_present():
    """Verify core ledger tools are registered."""
    names = [t["name"] for t in TOOL_DEFINITIONS]
    required_ledger = [
        "ledger_record",
        "ledger_outcome",
    ]
    for name in required_ledger:
        assert name in names, f"Core ledger tool missing from registry: {name}"


def test_core_substrate_tools_present():
    """Verify core substrate tools are registered."""
    names = [t["name"] for t in TOOL_DEFINITIONS]
    required_substrate = [
        "substrate_start_session",
        "substrate_end_session",
        "substrate_report",
    ]
    for name in required_substrate:
        assert name in names, f"Core substrate tool missing from registry: {name}"
