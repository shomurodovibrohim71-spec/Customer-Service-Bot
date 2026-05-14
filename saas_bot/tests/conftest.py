"""Pytest fixtures: make project root importable and provide tmp DBs."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    """Point DATA_DIR at a tmp path before the database module loads."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    # Force re-import so settings.DATA_DIR re-reads env.
    import importlib

    from config import settings

    importlib.reload(settings)
    from core import database

    importlib.reload(database)
    return tmp_path
