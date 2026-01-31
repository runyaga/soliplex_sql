"""Shared fixtures for functional tests with in-memory SQLite."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from soliplex_sql.adapter import SoliplexSQLAdapter
from soliplex_sql.config import SQLToolConfigBase
from soliplex_sql.tools import _adapter_cache

if TYPE_CHECKING:
    from sql_toolset_pydantic_ai import SQLDatabaseDeps


@pytest_asyncio.fixture
async def real_db() -> SQLDatabaseDeps:
    """Create in-memory SQLite database with test data.

    Creates a database with:
    - users table (id, name, email)
    - posts table (id, user_id FK, title, content)

    Yields:
        SQLDatabaseDeps configured for the test database
    """
    config = SQLToolConfigBase(
        tool_name="soliplex_sql.tools.query",
        database_url="sqlite:///:memory:",
        read_only=False,
        max_rows=100,
        query_timeout=30.0,
    )
    deps = config.create_deps()

    # Connect and create test tables
    await deps.database.connect()

    await deps.database.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE
        )
    """)

    await deps.database.execute("""
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Insert test data
    await deps.database.execute("""
        INSERT INTO users (name, email) VALUES
        ('Alice', 'alice@test.com'),
        ('Bob', 'bob@test.com'),
        ('Charlie', 'charlie@test.com')
    """)

    await deps.database.execute("""
        INSERT INTO posts (user_id, title, content) VALUES
        (1, 'First Post', 'Hello World'),
        (1, 'Second Post', 'More content'),
        (2, 'Bob Post', 'Bob writes here')
    """)

    yield deps

    await deps.database.close()


@pytest_asyncio.fixture
async def read_only_db() -> SQLDatabaseDeps:
    """Create read-only in-memory SQLite database with test data.

    Note: For in-memory SQLite, we create with read_only=True
    and test that the adapter's _check_read_only blocks mutations.
    The underlying in-memory db is still writable for setup.

    Yields:
        SQLDatabaseDeps configured as read-only
    """
    # Create in-memory db with write access for setup
    from sql_toolset_pydantic_ai import SQLDatabaseDeps
    from sql_toolset_pydantic_ai import SQLiteDatabase

    # Create writable backend for setup
    backend = SQLiteDatabase(":memory:", read_only=False)
    await backend.connect()

    await backend.execute("""
        CREATE TABLE items (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        )
    """)

    await backend.execute("""
        INSERT INTO items (name) VALUES ('Item1'), ('Item2')
    """)

    # Wrap in deps with read_only=True (adapter will enforce)
    deps = SQLDatabaseDeps(
        database=backend,
        read_only=True,
        max_rows=100,
        query_timeout=30.0,
    )

    yield deps

    await backend.close()


@pytest_asyncio.fixture
async def adapter(real_db: SQLDatabaseDeps) -> SoliplexSQLAdapter:
    """Create adapter with real database."""
    return SoliplexSQLAdapter(real_db)


@pytest_asyncio.fixture
async def read_only_adapter(
    read_only_db: SQLDatabaseDeps,
) -> SoliplexSQLAdapter:
    """Create read-only adapter."""
    return SoliplexSQLAdapter(read_only_db)


@pytest.fixture(autouse=True)
def clear_adapter_cache() -> None:
    """Clear adapter cache before each test."""
    _adapter_cache.clear()
    yield
    _adapter_cache.clear()
