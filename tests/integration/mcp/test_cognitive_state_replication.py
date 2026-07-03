from __future__ import annotations
import json
from pathlib import Path
import sys
import pytest
src_path = Path(__file__).resolve().parents[3] / 'src'
sys.path.insert(0, str(src_path))
from cognex.models import StateUnit
from cognex_mcp.context import CognexContext
from cognex_mcp.tools.dispatcher import handle_tool_call

@pytest.fixture(autouse=True)
def fresh_context(tmp_path):
    CognexContext.reset_instance()
    CognexContext.get_instance(db_path=str(tmp_path / 'cognex.db'), project='test-project')
    yield
    CognexContext.reset_instance()

@pytest.mark.asyncio
async def test_provenance_round_trip_and_cycle_prevention():
    first = await handle_tool_call('unit_commit', {'content': 'Use SQLite as the local state store', 'project': 'test-project'})
    second = await handle_tool_call('unit_commit', {'content': 'Keep migrations append-only', 'project': 'test-project'})
    link = await handle_tool_call('provenance_link', {'from_ref': first['unit_id'], 'to_ref': second['unit_id'], 'edge_type': 'derived_from', 'rationale': 'migration policy follows the local store decision'})
    assert link['edge_type'] == 'derived_from'
    trace = await handle_tool_call('provenance_trace', {'node_or_ref_id': second['unit_id'], 'direction': 'origins', 'depth': 2})
    assert trace['found'] is True
    assert trace['tree']['children'][0]['ref'].endswith(first['unit_id'])
    with pytest.raises(ValueError, match='cycle'):
        await handle_tool_call('provenance_link', {'from_ref': second['unit_id'], 'to_ref': first['unit_id'], 'edge_type': 'derived_from'})

@pytest.mark.asyncio
async def test_ledger_alternatives_create_counterfactual_nodes():
    decision = await handle_tool_call('ledger_record', {'tool_used': 'sqlite', 'alternatives': ['postgres', 'redis'], 'reasoning': 'single-file local persistence is enough', 'project': 'test-project'})
    ctx = CognexContext.get_instance()
    with ctx.unit_store._connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM provenance_nodes WHERE node_type = 'alternative' AND ref_id LIKE ?", (f"{decision['decision_id']}:%",)).fetchone()[0]
        rejected = conn.execute("SELECT COUNT(*) FROM provenance_edges WHERE edge_type = 'rejected_because'").fetchone()[0]
    assert count == 2
    assert rejected == 2

@pytest.mark.asyncio
async def test_epistemic_downgrade_cascades_on_override():
    base = await handle_tool_call('unit_commit', {'content': 'API contract is stable', 'project': 'test-project', 'epistemic_status': 'verified'})
    dependent = await handle_tool_call('unit_commit', {'content': 'Client can rely on the stable API contract', 'project': 'test-project', 'epistemic_status': 'verified', 'depends_on': [base['unit_id']]})
    await handle_tool_call('unit_mark_overridden', {'unit_id': base['unit_id']})
    ctx = CognexContext.get_instance()
    dep = ctx.unit_store.get(dependent['unit_id'])
    deltas = ctx.unit_store.get_deltas(dependent['unit_id'])
    assert dep is not None
    assert dep.epistemic_status == 'assumed'
    assert any((d['reason'] == f"dependency_overridden:{base['unit_id']}" for d in deltas))

@pytest.mark.asyncio
async def test_integrity_signature_and_ref_failure_for_missing_record():
    await handle_tool_call('memory_add', {'content': 'Merkle roots are signed', 'project': 'test-project'})
    ok = await handle_tool_call('integrity_verify', {'project': 'test-project'})
    assert ok['verified'] is True
    assert ok['signature_valid'] is True
    missing = await handle_tool_call('integrity_verify', {'project': 'test-project', 'ref_ids': ['does-not-exist']})
    assert missing['verified'] is False

@pytest.mark.asyncio
async def test_handoff_signature_fails_closed_when_tampered():
    created = await handle_tool_call('handoff_create', {'project': 'test-project', 'goal_stack': ['finish cognitive state replication'], 'in_flight_ops': ['run tests'], 'notes': 'compact manifest'})
    manifest = created['manifest']
    assert len(created['serialized'].split()) < 2000
    ready = await handle_tool_call('handoff_resume', {'manifest_json': json.dumps(manifest)})
    assert ready['status'] == 'ready'
    manifest['goal_stack'] = ['tampered']
    failed = await handle_tool_call('handoff_resume', {'manifest_json': json.dumps(manifest)})
    assert failed['status'] == 'failed'

def test_reconciliation_classifies_new_identical_and_conflict():
    ctx = CognexContext.get_instance()
    local = StateUnit(unit_id='local-unit', content='The auth token must stay server side', project='test-project', scope='auth')
    ctx.unit_store.save(local)
    report = ctx.reconciler.classify_units([{'unit_id': 'same-unit', 'content': 'The auth token must stay server side', 'project': 'test-project', 'scope': 'auth'}, {'unit_id': 'conflicting-unit', 'content': 'The auth token can stay client side', 'project': 'test-project', 'scope': 'auth'}, {'unit_id': 'new-unit', 'content': 'Use short lived refresh tokens', 'project': 'test-project', 'scope': 'auth'}])
    assert len(report['identical']) == 1
    assert len(report['conflicts']) == 1
    assert len(report['new']) == 1