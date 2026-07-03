import pytest
from pathlib import Path
import sys
import shutil
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

@pytest.fixture
def tmp_db(tmp_path):
    db_path = tmp_path / 'test.db'
    yield db_path
    if db_path.exists():
        try:
            shutil.rmtree(db_path.parent)
        except:
            pass