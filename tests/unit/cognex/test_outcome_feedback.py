from datetime import datetime, timezone
import struct
from unittest.mock import patch
import pytest
from cognex.audit import AuditLog
from cognex.feedback import OutcomeFeedback
from cognex.models import MemoryEntry
from cognex.store import MemoryStore

@pytest.fixture
def temp_dbs(tmp_path):
    db_file = tmp_path / 'test.db'
    store = MemoryStore(db_path=db_file)
    audit = AuditLog(db_path=db_file)
    yield (store, audit)
    store.close()
    audit._pool.close_all()

def test_outcome_feedback_boosting_and_penalizing(temp_dbs):
    store, audit = temp_dbs
    m = MemoryEntry(id='m1', content='test content', relevance_score=1.0)
    store.save(m)
    with store._connect() as conn:
        store._log_access(conn, 's1', 'm1')
        conn.commit()
    OutcomeFeedback.apply_outcome_feedback(session_id='s1', success=True, store=store, ledger=None, audit=audit)
    with store._connect() as conn:
        row = conn.execute("SELECT relevance_score FROM memories WHERE id='m1'").fetchone()
        assert row['relevance_score'] == pytest.approx(1.05)
    OutcomeFeedback.apply_outcome_feedback(session_id='s1', success=False, store=store, ledger=None, audit=audit)
    with store._connect() as conn:
        row = conn.execute("SELECT relevance_score FROM memories WHERE id='m1'").fetchone()
        assert row['relevance_score'] == pytest.approx(1.02)
    with audit._pool.get_connection() as conn:
        row = conn.execute("SELECT event_type, payload FROM audit_log WHERE event_type='outcome_feedback'").fetchone()
        assert row is not None
        assert 'm1' in row['payload']

def test_decay_uniqueness_modifiers(temp_dbs):
    store, _ = temp_dbs
    memories = [MemoryEntry(id=f'm{i}', content=f'content {i}') for i in range(10)]
    store.save_many(memories)
    with patch('cognex.embeddings.EmbeddingEngine.AVAILABLE', True):
        with store._connect() as conn:
            for i in range(10):
                vec = [0.0] * 384
                if i < 9:
                    vec[0] = 1.0
                else:
                    vec[1] = 1.0
                blob = struct.pack('384f', *vec)
                conn.execute('INSERT INTO memory_embeddings (memory_id, embedding, model_name, created_at) VALUES (?, ?, ?, ?)', (f'm{i}', blob, 'mock-model', datetime.now(timezone.utc).isoformat()))
            conn.commit()
        modifiers = OutcomeFeedback.compute_uniqueness_modifiers(store)
        assert len(modifiers) == 10
        assert modifiers['m9'] == 0.85
        assert modifiers['m0'] == 1.05