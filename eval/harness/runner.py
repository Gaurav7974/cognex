"""LongMemEval evaluation harness — test case loader for Cognex.

Calls the engine layer directly instead of going through the MCP tool
dispatcher. This avoids the dispatcher's shared thread pool, whose
thread-local DB connections leak between cases and cause SQLite lock
contention. Direct calls run in the eval's own thread with a single
connection per store, which is both faster and cleaner for isolated
per-case evaluation.
"""

import sys
from pathlib import Path

src_path = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(src_path))

from cognex_mcp.context import CognexContext
from cognex import MemoryType, MemoryScope


def _format_transcript(turns: list[dict]) -> str:
    """Format setup_turns into a readable conversation transcript."""
    lines = []
    for turn in turns:
        role = "User" if turn.get("role") == "user" else "Assistant"
        lines.append(f"{role}: {turn.get('content', '')}")
    return "\n".join(lines)


def load_case(case: dict, tmp_db_path: str) -> None:
    """Load a single test case into a fresh, isolated Cognex context.

    Each case gets its own database and its own session. The setup_turns
    are processed through the transcript extractor so that realistic
    session memories are created — different per case, derived from the
    actual conversation rather than a single hardcoded string. The
    ground-truth memory and distractors are then stored within that
    session context.
    """
    CognexContext.reset_instance()
    ctx = CognexContext.get_instance(db_path=tmp_db_path, project=case["project"])

    session_id = f"eval-{case['id']}"

    # Start an isolated session for this case
    ctx.engine.start_session(session_id=session_id, project=case["project"])

    # Process setup_turns through the transcript extractor.
    # This creates realistic session memories that differ per case,
    # derived from the actual conversation context.
    setup_turns = case.get("setup_turns", [])
    if setup_turns:
        transcript = _format_transcript(setup_turns)
        ctx.engine.process_transcript(
            transcript=transcript,
            session_id=session_id,
            project=case["project"],
        )

    # Store the ground-truth memory within this session
    ctx.engine.add_memory(
        content=case["memory_to_store"],
        memory_type=MemoryType.FACT,
        project=case["project"],
    )

    # Store distractor memories to increase retrieval difficulty
    for distractor in case.get("distractor_memories", []):
        ctx.engine.add_memory(
            content=distractor,
            memory_type=MemoryType.FACT,
            project=case["project"],
        )

    # End the session — snapshot is saved, memories persist in DB
    ctx.engine.end_session(
        summary=f"Eval case {case['id']}: {case.get('category', 'unknown')}",
    )
