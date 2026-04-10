"""Shared fixtures for stress tests."""

import pytest
from pathlib import Path
import sys
import shutil

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from substrate import CognitiveSubstrate


@pytest.fixture
def stress_substrate(tmp_path):
    """Create a test substrate instance for stress tests."""
    db_path = tmp_path / "stress_substrate.db"
    sub = CognitiveSubstrate(db_path=db_path)
    yield sub
    # Cleanup
    if db_path.exists():
        try:
            shutil.rmtree(db_path.parent)
        except:
            pass
