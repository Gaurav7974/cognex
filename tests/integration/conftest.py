"""Shared fixtures for integration tests."""

import pytest
from pathlib import Path
import sys
import shutil

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from substrate import CognitiveSubstrate


@pytest.fixture
def substrate(tmp_path):
    """Create a test substrate instance."""
    db_path = tmp_path / "substrate.db"
    sub = CognitiveSubstrate(db_path=db_path)
    yield sub
    # Cleanup
    if db_path.exists():
        try:
            shutil.rmtree(db_path.parent)
        except:
            pass


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary database for integration tests."""
    db_path = tmp_path / "test.db"
    yield db_path
    # Cleanup
    if db_path.exists():
        try:
            shutil.rmtree(db_path.parent)
        except:
            pass
