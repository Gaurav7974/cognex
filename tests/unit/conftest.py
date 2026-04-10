"""Shared fixtures for unit tests."""

import pytest
from pathlib import Path
import sys
import shutil

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary database for unit tests."""
    db_path = tmp_path / "test.db"
    yield db_path
    # Cleanup
    if db_path.exists():
        try:
            shutil.rmtree(db_path.parent)
        except:
            pass
