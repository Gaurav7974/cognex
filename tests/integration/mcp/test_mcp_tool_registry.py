import pytest
import sys
from pathlib import Path

src_path = Path(__file__).resolve().parents[3] / "src"
sys.path.insert(0, str(src_path))

from cognex_mcp.tools.registry import TOOL_DEFINITIONS


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


def test_core_cognex_tools_present():
    """Verify core engine tools are registered."""
    names = [t["name"] for t in TOOL_DEFINITIONS]
    required_cognex = [
        "cognex_start_session",
        "cognex_end_session",
        "cognex_report",
    ]
    for name in required_cognex:
        assert name in names, f"Core engine tool missing from registry: {name}"


def test_audit_tools_present():
    """Verify Phase 3a audit tools are registered."""
    names = [t["name"] for t in TOOL_DEFINITIONS]
    required_audit = ["audit_get_recent", "audit_verify"]
    for name in required_audit:
        assert name in names, f"Audit tool missing from registry: {name}"


def test_unit_and_teleport_tools_present():
    """Verify cognitive unit and teleport tools are registered."""
    names = [t["name"] for t in TOOL_DEFINITIONS]
    required = [
        "unit_commit",
        "unit_mark_overridden",
        "teleport_create_bundle",
        "teleport_rehydrate",
    ]
    for name in required:
        assert name in names, f"Tool missing from registry: {name}"


def test_tool_count_is_40():
    """Verify total tool count is exactly 40 (added consolidator, arcs, health, audit chain, and sync tools)."""
    assert len(TOOL_DEFINITIONS) == 40, (
        f"Expected 40 tools, got {len(TOOL_DEFINITIONS)}. "
        f"Tools: {sorted([t['name'] for t in TOOL_DEFINITIONS])}"
    )
