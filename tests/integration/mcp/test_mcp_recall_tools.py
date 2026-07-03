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

async def _seed():
    await handle_tool_call('memory_add', {'content': 'prefer pytest over unittest', 'project': 'p1'})
    await handle_tool_call('memory_add', {'content': 'use FastAPI for rest apis', 'memory_type': 'decision', 'project': 'p1'})
    await handle_tool_call('unit_commit', {'content': 'decided on postgres', 'project': 'p1', 'unit_type': 'decision'})
    await handle_tool_call('ledger_record', {'tool_used': 'psql', 'reasoning': 'postgres scales well', 'project': 'p1'})

@pytest.mark.asyncio
async def test_recall_snippets_default():
    await _seed()
    result = await handle_tool_call('recall', {'query': 'pytest', 'kind': 'memory'})
    assert result['detail'] == 'snippets'
    assert result['count'] >= 1
    hit = result['memories'][0]
    assert 'id' in hit
    assert 'gist' in hit
    assert 'score' in hit
    assert 'date' in hit
    assert 'type' in hit
    assert 'content' not in hit

@pytest.mark.asyncio
async def test_recall_ids_detail():
    await _seed()
    result = await handle_tool_call('recall', {'query': 'pytest', 'kind': 'memory', 'detail': 'ids'})
    assert result['count'] >= 1
    hit = result['memories'][0]
    assert 'id' in hit
    assert 'gist' not in hit
    assert 'content' not in hit

@pytest.mark.asyncio
async def test_recall_full_detail():
    await _seed()
    result = await handle_tool_call('recall', {'query': 'pytest', 'kind': 'memory', 'detail': 'full'})
    assert result['count'] >= 1
    hit = result['memories'][0]
    assert 'content' in hit
    assert 'scope' in hit
    assert 'project' in hit

@pytest.mark.asyncio
async def test_recall_all_kind():
    await _seed()
    result = await handle_tool_call('recall', {'query': 'postgres', 'kind': 'all', 'detail': 'full'})
    assert result['count'] >= 1
    assert 'results' in result
    types_found = {h['type'] for h in result['results']}
    assert 'decision' in types_found or 'unit' in types_found

@pytest.mark.asyncio
async def test_recall_unit_kind():
    await _seed()
    result = await handle_tool_call('recall', {'query': 'postgres', 'kind': 'unit', 'detail': 'full'})
    assert result['count'] >= 1
    assert 'units' in result

@pytest.mark.asyncio
async def test_recall_decision_kind():
    await _seed()
    result = await handle_tool_call('recall', {'query': 'postgres', 'kind': 'decision', 'detail': 'full'})
    assert result['count'] >= 1
    assert 'decisions' in result

@pytest.mark.asyncio
async def test_recall_filters_project():
    await handle_tool_call('memory_add', {'content': 'alpha project memory', 'project': 'alpha'})
    await handle_tool_call('memory_add', {'content': 'beta project memory', 'project': 'beta'})
    result = await handle_tool_call('recall', {'query': 'project', 'kind': 'memory', 'detail': 'full', 'filters': {'project': 'alpha'}})
    assert all((h.get('project') == 'alpha' for h in result['memories']))

@pytest.mark.asyncio
async def test_recall_compact_similar_collapse():
    for _ in range(3):
        await handle_tool_call('memory_add', {'content': 'prefer pytest over unittest', 'project': 'p1'})
    result = await handle_tool_call('recall', {'query': 'pytest', 'kind': 'memory', 'detail': 'snippets'})
    assert result['count'] >= 1

@pytest.mark.asyncio
async def test_recall_limit_respected():
    for i in range(15):
        await handle_tool_call('memory_add', {'content': f'memory number {i} about testing', 'project': 'p1'})
    result = await handle_tool_call('recall', {'query': 'testing', 'kind': 'memory', 'limit': 3})
    assert result['count'] <= 3

@pytest.mark.asyncio
async def test_trust_query_with_tool_name():
    await handle_tool_call('trust_record', {'action': 'approval', 'tool_name': 'MyTool', 'project': 'p1'})
    result = await handle_tool_call('trust_query', {'tool_name': 'MyTool', 'project': 'p1'})
    assert result['tool_name'] == 'MyTool'
    assert 'requires_approval' in result
    assert 'trust_level' in result

@pytest.mark.asyncio
async def test_trust_query_summary_no_tool_name():
    await handle_tool_call('trust_record', {'action': 'approval', 'tool_name': 'ToolA', 'project': 'p1'})
    result = await handle_tool_call('trust_query', {'project': 'p1'})
    assert 'records' in result
    assert result['count'] >= 1

@pytest.mark.asyncio
async def test_trust_manage_record():
    result = await handle_tool_call('trust_manage', {'action': 'approval', 'tool_name': 'NewTool', 'project': 'p1'})
    assert result['action'] == 'approval'
    assert result['tool_name'] == 'NewTool'

@pytest.mark.asyncio
async def test_trust_manage_summary_no_action():
    await handle_tool_call('trust_manage', {'action': 'approval', 'tool_name': 'X', 'project': 'p1'})
    result = await handle_tool_call('trust_manage', {'project': 'p1'})
    assert 'records' in result
    assert result['count'] >= 1

@pytest.mark.asyncio
async def test_deprecated_memory_search_still_works():
    await _seed()
    result = await handle_tool_call('memory_search', {'query': 'pytest', 'project': 'p1'})
    assert result['count'] >= 1
    assert any(('pytest' in m['content'].lower() for m in result['memories']))

@pytest.mark.asyncio
async def test_deprecated_trust_check_still_works():
    await handle_tool_call('trust_record', {'action': 'approval', 'tool_name': 'T', 'project': 'p1'})
    result = await handle_tool_call('trust_check', {'tool_name': 'T', 'project': 'p1'})
    assert 'requires_approval' in result

@pytest.mark.asyncio
async def test_chp_tools_not_registered_without_env():
    from cognex_mcp.tools.dispatcher import TOOL_HANDLERS
    assert 'chp_create_channel' not in TOOL_HANDLERS
    assert 'chp_transfer' not in TOOL_HANDLERS
    assert 'chp_project' not in TOOL_HANDLERS