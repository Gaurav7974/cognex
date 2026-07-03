from __future__ import annotations
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
from cognex import CognexEngine, MemoryStore

@pytest.fixture
def tmp_db(tmp_path):
    return str(tmp_path / 'test.db')

@pytest.fixture
def store(tmp_db):
    return MemoryStore(db_path=tmp_db)

@pytest.fixture
def engine(tmp_db):
    return CognexEngine(db_path=tmp_db)