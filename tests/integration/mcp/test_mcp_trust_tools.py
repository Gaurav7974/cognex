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
async def test_unknown_tool_requires_approval():
    result = await handle_tool_call('trust_check', {'tool_name': 'brand_new_tool'})
    assert result['requires_approval'] is True

@pytest.mark.asyncio
async def test_five_approvals_reaches_observed():
    for _ in range(5):
        await handle_tool_call('trust_record', {'action': 'approval', 'tool_name': 'file_writer', 'project': 'test-project'})
    result = await handle_tool_call('trust_check', {'tool_name': 'file_writer', 'project': 'test-project'})
    assert result['requires_approval'] is False

@pytest.mark.asyncio
async def test_violation_blocks_tool():
    await handle_tool_call('trust_record', {'action': 'violation', 'tool_name': 'shell'})
    result = await handle_tool_call('trust_check', {'tool_name': 'shell'})
    assert result['requires_approval'] is True

@pytest.mark.asyncio
async def test_trust_summary_returns_list():
    await handle_tool_call('trust_record', {'action': 'approval', 'tool_name': 'toolA'})
    await handle_tool_call('trust_record', {'action': 'approval', 'tool_name': 'toolB'})
    result = await handle_tool_call('trust_summary', {})
    assert 'records' in result or 'count' in result
    assert result.get('count', len(result.get('records', []))) >= 2

@pytest.mark.asyncio
async def test_trust_record_approval_increments_count():
    await handle_tool_call('trust_record', {'action': 'approval', 'tool_name': 'BashTool', 'project': 'test-project', 'reason': 'Test approval'})
    result = await handle_tool_call('trust_check', {'tool_name': 'BashTool', 'project': 'test-project'})
    assert result.get('approval_count', 0) >= 1

@pytest.mark.asyncio
async def test_trust_check_returns_required_fields():
    result = await handle_tool_call('trust_check', {'tool_name': 'FileTool'})
    assert 'requires_approval' in result
    assert 'trust_level' in result or 'trust_score' in result