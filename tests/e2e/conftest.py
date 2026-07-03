import pytest
from pathlib import Path
import sys
import shutil
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))
from cognex import CognexEngine

@pytest.fixture
def engine(tmp_path):
    db_path = tmp_path / 'e2e_cognex.db'
    eng = CognexEngine(db_path=db_path)
    yield eng
    if db_path.exists():
        try:
            shutil.rmtree(db_path.parent)
        except:
            pass

@pytest.fixture
def tmp_project_dir(tmp_path):
    project_dir = tmp_path / 'test_project'
    project_dir.mkdir(exist_ok=True)
    yield project_dir
    if project_dir.exists():
        try:
            shutil.rmtree(project_dir)
        except:
            pass