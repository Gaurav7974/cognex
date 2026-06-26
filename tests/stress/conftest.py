"""Shared fixtures for stress tests."""

import pytest
from pathlib import Path
import sys
import shutil

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cognex import CognexEngine


@pytest.fixture
def stress_engine(tmp_path):
    """Create a test engine instance for stress tests."""
    db_path = tmp_path / "stress_cognex.db"
    eng = CognexEngine(db_path=db_path)
    yield eng
    # Cleanup
    if db_path.exists():
        try:
            shutil.rmtree(db_path.parent)
        except:
            pass
