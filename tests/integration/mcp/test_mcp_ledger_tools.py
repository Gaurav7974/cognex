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
async def test_ledger_record_basic():
    result = await handle_tool_call('ledger_record', {'tool_used': 'pytest', 'reasoning': 'needed tests', 'project': 'test-project'})
    assert 'id' in result or 'decision_id' in result
    assert result['tool_used'] == 'pytest'

@pytest.mark.asyncio
async def test_ledger_record_with_alternatives():
    result = await handle_tool_call('ledger_record', {'tool_used': 'EditTool', 'alternatives': ['ReadTool', 'BashTool'], 'reasoning': 'Best for this task', 'project': 'test-project'})
    assert 'id' in result or 'decision_id' in result
    decision_id = result.get('id') or result.get('decision_id')
    assert decision_id is not None

@pytest.mark.asyncio
async def test_ledger_outcome_updates_decision():
    record = await handle_tool_call('ledger_record', {'tool_used': 'BashTool'})
    decision_id = record.get('id') or record.get('decision_id')
    result = await handle_tool_call('ledger_outcome', {'decision_id': decision_id, 'outcome': 'worked great', 'success': True})
    assert result['outcome'] == 'worked great'
    assert result.get('success') is True or result.get('outcome_success') is True

@pytest.mark.asyncio
async def test_ledger_find_similar_returns_results():
    for _ in range(3):
        await handle_tool_call('ledger_record', {'tool_used': 'BashTool', 'context': 'database migration issue'})
    result = await handle_tool_call('ledger_find_similar', {'query': 'database migration'})
    assert 'count' in result or 'results' in result
    assert result.get('count', len(result.get('results', []))) >= 1

@pytest.mark.asyncio
async def test_ledger_outcome_returns_expected_fields():
    record = await handle_tool_call('ledger_record', {'tool_used': 'FileTool', 'context': 'file operation'})
    decision_id = record.get('id') or record.get('decision_id')
    result = await handle_tool_call('ledger_outcome', {'decision_id': decision_id, 'outcome': 'test result', 'success': False})
    assert 'outcome' in result
    assert result.get('success', False) is False

@pytest.mark.asyncio
async def test_ledger_record_creates_unique_ids():
    r1 = await handle_tool_call('ledger_record', {'tool_used': 'Tool1'})
    r2 = await handle_tool_call('ledger_record', {'tool_used': 'Tool2'})
    id1 = r1.get('id') or r1.get('decision_id')
    id2 = r2.get('id') or r2.get('decision_id')
    assert id1 != id2