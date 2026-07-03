import pytest
from pathlib import Path
import sys
import shutil
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))
from cognex import CognexEngine

@pytest.fixture
def engine(tmp_path):
    db_path = tmp_path / 'cognex.db'
    eng = CognexEngine(db_path=db_path)
    yield eng
    if db_path.exists():
        try:
            shutil.rmtree(db_path.parent)
        except:
            pass

@pytest.fixture
def tmp_db(tmp_path):
    db_path = tmp_path / 'test.db'
    yield db_path
    if db_path.exists():
        try:
            shutil.rmtree(db_path.parent)
        except:
            pass