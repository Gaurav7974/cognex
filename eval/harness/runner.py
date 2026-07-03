import sys
from pathlib import Path
src_path = Path(__file__).resolve().parents[2] / 'src'
sys.path.insert(0, str(src_path))
from cognex_mcp.context import CognexContext
from cognex import MemoryType, MemoryScope

def _format_transcript(turns: list[dict]) -> str:
    lines = []
    for turn in turns:
        role = 'User' if turn.get('role') == 'user' else 'Assistant'
        lines.append(f"{role}: {turn.get('content', '')}")
    return '\n'.join(lines)

def load_case(case: dict, tmp_db_path: str) -> None:
    CognexContext.reset_instance()
    ctx = CognexContext.get_instance(db_path=tmp_db_path, project=case['project'])
    session_id = f"eval-{case['id']}"
    ctx.engine.start_session(session_id=session_id, project=case['project'])
    setup_turns = case.get('setup_turns', [])
    if setup_turns:
        transcript = _format_transcript(setup_turns)
        ctx.engine.process_transcript(transcript=transcript, session_id=session_id, project=case['project'])
    ctx.engine.add_memory(content=case['memory_to_store'], memory_type=MemoryType.FACT, project=case['project'])
    for distractor in case.get('distractor_memories', []):
        ctx.engine.add_memory(content=distractor, memory_type=MemoryType.FACT, project=case['project'])
    ctx.engine.end_session(summary=f"Eval case {case['id']}: {case.get('category', 'unknown')}")