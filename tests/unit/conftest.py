"""Shared fixtures for unit tests."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def temp_db_path() -> Path:
    """Create a temporary database file path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        return Path(f.name)


@pytest.fixture
def mock_ctx() -> MagicMock:
    """Create a mock RunContext with deps."""
    ctx = MagicMock()
    ctx.deps = MagicMock()
    ctx.deps.tool_configs = {}
    return ctx


@pytest.fixture
def mock_database() -> MagicMock:
    """Create a mock database backend."""
    db = MagicMock()
    db.get_tables = MagicMock(return_value=["users", "posts"])
    db.get_schema = MagicMock()
    db.get_table_info = MagicMock()
    db.execute = MagicMock()
    db.explain = MagicMock()
    db.close = MagicMock()
    return db


@pytest.fixture
def mock_sql_deps(mock_database: MagicMock) -> MagicMock:
    """Create mock SQLDatabaseDeps."""
    deps = MagicMock()
    deps.database = mock_database
    deps.read_only = True
    deps.max_rows = 100
    deps.query_timeout = 30.0
    return deps
