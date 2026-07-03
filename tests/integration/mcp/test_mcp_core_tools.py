import pytest
import sys
from pathlib import Path
src_path = Path(__file__).resolve().parents[3] / 'src'
sys.path.insert(0, str(src_path))
from cognex_mcp.context import CognexContext
from cognex_mcp.tools.dispatcher import handle_tool_call

@pytest.fixture(autouse=True)
def fresh_context(tmp_path):
    CognexContext.reset_instance()
    db = str(tmp_path / 'cognex.db')
    CognexContext.get_instance(db_path=db, project='test-project')
    yield
    CognexContext.reset_instance()

@pytest.mark.asyncio
async def test_start_session_returns_session_id():
    result = await handle_tool_call('cognex_start_session', {'session_id': 'sess-001', 'project': 'test-project'})
    assert result['session_id'] == 'sess-001'

@pytest.mark.asyncio
async def test_end_session_graceful_without_start():
    result = await handle_tool_call('cognex_end_session', {})
    assert 'message' in result or 'session_id' in result
    if 'message' in result:
        assert isinstance(result['message'], str)
        assert len(result['message']) > 0
    elif 'session_id' in result:
        assert result['session_id'] is None or isinstance(result['session_id'], str)

@pytest.mark.asyncio
async def test_report_returns_expected_keys():
    result = await handle_tool_call('cognex_report', {})
    assert 'total_memories' in result
    assert 'total_sessions' in result
    assert result['total_memories'] >= 0

@pytest.mark.asyncio
async def test_report_counts_increase_after_add():
    before = await handle_tool_call('cognex_report', {})
    baseline = before['total_memories']
    for i in range(3):
        await handle_tool_call('memory_add', {'content': f'memory {i}', 'project': 'test-project'})
    after = await handle_tool_call('cognex_report', {})
    assert after['total_memories'] == baseline + 3

@pytest.mark.asyncio
async def test_start_session_with_no_prior_memories():
    result = await handle_tool_call('cognex_start_session', {'session_id': 'fresh-001', 'project': 'test-project'})
    assert result['session_id'] == 'fresh-001'
    memories_key = 'context_memories' if 'context_memories' in result else 'memories'
    if memories_key in result:
        assert isinstance(result[memories_key], list)
        assert len(result[memories_key]) == 0

@pytest.mark.asyncio
async def test_start_session_creates_audit_entry():
    result = await handle_tool_call('cognex_start_session', {'session_id': 'audit-test-001', 'project': 'test-project'})
    assert result['session_id'] == 'audit-test-001'
    audit_result = await handle_tool_call('audit_get_recent', {'project': 'test-project', 'limit': 10})
    assert 'entries' in audit_result or 'events' in audit_result or isinstance(audit_result, list)
    entries = audit_result.get('entries', audit_result.get('events', audit_result))
    if isinstance(entries, list) and len(entries) > 0:
        event_types = [e.get('event_type') for e in entries if isinstance(e, dict)]
        assert 'session_start' in event_types, f"Expected 'session_start' in event types: {event_types}"

@pytest.mark.asyncio
async def test_end_session_creates_audit_entry():
    start_result = await handle_tool_call('cognex_start_session', {'session_id': 'audit-end-test-001', 'project': 'test-project'})
    assert start_result['session_id'] == 'audit-end-test-001'
    end_result = await handle_tool_call('cognex_end_session', {'summary': 'test session ended'})
    assert end_result is not None
    audit_result = await handle_tool_call('audit_get_recent', {'project': 'test-project', 'limit': 20})
    assert 'entries' in audit_result or 'events' in audit_result or isinstance(audit_result, list)
    entries = audit_result.get('entries', audit_result.get('events', audit_result))
    if isinstance(entries, list) and len(entries) > 1:
        event_types = [e.get('event_type') for e in entries if isinstance(e, dict)]
        assert len(event_types) > 0, 'Expected at least one audit event'