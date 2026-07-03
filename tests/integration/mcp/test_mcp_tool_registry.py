import pytest
import sys
from pathlib import Path
src_path = Path(__file__).resolve().parents[3] / 'src'
sys.path.insert(0, str(src_path))
from cognex_mcp.tools.registry import TOOL_DEFINITIONS

def test_all_tools_have_required_fields():
    for tool in TOOL_DEFINITIONS:
        assert 'name' in tool, f'Tool missing name: {tool}'
        assert 'description' in tool, f"Tool {tool.get('name', '?')} missing description"
        assert 'inputSchema' in tool, f"Tool {tool.get('name', '?')} missing inputSchema"

def test_no_duplicate_tool_names():
    names = [t['name'] for t in TOOL_DEFINITIONS]
    assert len(names) == len(set(names)), f'Duplicate tool names found: {[n for n in names if names.count(n) > 1]}'

def test_tool_registry_not_empty():
    assert len(TOOL_DEFINITIONS) > 0, 'Tool registry is empty'

def test_core_memory_tools_present():
    names = [t['name'] for t in TOOL_DEFINITIONS]
    required_core = ['memory_add', 'recall', 'memory_decay']
    for name in required_core:
        assert name in names, f'Core memory tool missing from registry: {name}'

def test_core_trust_tools_present():
    names = [t['name'] for t in TOOL_DEFINITIONS]
    required_trust = ['trust_check', 'trust_record']
    for name in required_trust:
        assert name in names, f'Core trust tool missing from registry: {name}'

def test_core_ledger_tools_present():
    names = [t['name'] for t in TOOL_DEFINITIONS]
    required_ledger = ['ledger_record', 'ledger_outcome']
    for name in required_ledger:
        assert name in names, f'Core ledger tool missing from registry: {name}'

def test_core_cognex_tools_present():
    names = [t['name'] for t in TOOL_DEFINITIONS]
    required_cognex = ['cognex_start_session', 'cognex_end_session', 'cognex_report']
    for name in required_cognex:
        assert name in names, f'Core engine tool missing from registry: {name}'

def test_audit_tools_present():
    names = [t['name'] for t in TOOL_DEFINITIONS]
    required_audit = ['audit_get_recent', 'audit_verify_chain']
    for name in required_audit:
        assert name in names, f'Audit tool missing from registry: {name}'

def test_unit_and_teleport_tools_present():
    names = [t['name'] for t in TOOL_DEFINITIONS]
    required = ['unit_commit', 'unit_mark_overridden', 'teleport_create_bundle', 'teleport_rehydrate', 'handoff_create', 'handoff_resume']
    for name in required:
        assert name in names, f'Tool missing from registry: {name}'

def test_consolidated_tools_present():
    names = [t['name'] for t in TOOL_DEFINITIONS]
    for name in ['recall', 'trust_query', 'trust_manage', 'integrity_verify']:
        assert name in names, f'Consolidated tool missing from registry: {name}'

def test_cognitive_state_replication_tools_present():
    names = [t['name'] for t in TOOL_DEFINITIONS]
    for name in ['provenance_trace', 'provenance_link', 'question_raise', 'question_resolve', 'integrity_verify', 'handoff_create', 'handoff_resume', 'reconcile_resolve', 'note_reasoning']:
        assert name in names, f'Cognitive replication tool missing from registry: {name}'

def test_chp_tools_not_registered_by_default():
    names = [t['name'] for t in TOOL_DEFINITIONS]
    for name in ['chp_create_channel', 'chp_transfer', 'chp_project']:
        assert name not in names, f'CHP tool {name} should not be registered by default'

def test_deprecated_aliases_present():
    names = [t['name'] for t in TOOL_DEFINITIONS]
    for name in ['trust_check', 'trust_record']:
        assert name in names, f'Deprecated alias missing from registry: {name}'

def test_tool_count_does_not_exceed_41():
    assert len(TOOL_DEFINITIONS) <= 41, f"Expected at most 41 tools, got {len(TOOL_DEFINITIONS)}. Tools: {sorted([t['name'] for t in TOOL_DEFINITIONS])}"