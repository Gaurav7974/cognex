"""Shared fixtures for end-to-end tests."""

import pytest
from pathlib import Path
import sys
import shutil

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from substrate import CognitiveSubstrate


@pytest.fixture
def substrate(tmp_path):
    """Create a test substrate instance for E2E tests."""
    db_path = tmp_path / "e2e_substrate.db"
    sub = CognitiveSubstrate(db_path=db_path)
    yield sub
    # Cleanup
    if db_path.exists():
        try:
            shutil.rmtree(db_path.parent)
        except:
            pass


@pytest.fixture
def tmp_project_dir(tmp_path):
    """Create a temporary project directory for E2E tests."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir(exist_ok=True)
    yield project_dir
    # Cleanup
    if project_dir.exists():
        try:
            shutil.rmtree(project_dir)
        except:
            pass
