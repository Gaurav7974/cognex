import sys
from pathlib import Path

src_path = Path(__file__).resolve().parents[3] / "src"
sys.path.insert(0, str(src_path))


def test_all_tools_registered():
    expected_tools = [
        "substrate_start_session",
        "substrate_end_session",
        "substrate_process_transcript",
        "substrate_report",
        "memory_add",
        "memory_search",
        "memory_get_context",
        "memory_decay",
        "trust_check",
        "trust_record",
        "trust_get",
        "trust_summary",
        "ledger_record",
        "ledger_outcome",
        "ledger_find_similar",
        "teleport_create_bundle",
        "teleport_rehydrate",
        "swarm_compile_intent",
    ]

    from substrate_mcp.tools import TOOL_HANDLERS

    actual_tools = list(TOOL_HANDLERS.keys())
    for tool in expected_tools:
        assert tool in actual_tools, f"Missing tool: {tool}"
    assert len(actual_tools) == len(expected_tools)


if __name__ == "__main__":
    test_all_tools_registered()
