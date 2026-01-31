"""Integration tests for write operations (INSERT, UPDATE, DELETE).

These tests verify that write operations actually persist to the database.
They test the full flow: tool_config -> adapter -> backend -> database.

Issue discovered: The upstream sql-toolset-pydantic-ai SQLiteDatabase
does not call commit() after write operations, causing changes to be lost.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from soliplex_sql.adapter import SoliplexSQLAdapter
from soliplex_sql.config import SQLToolConfig
from soliplex_sql.tools import _adapter_cache

if TYPE_CHECKING:
    from sql_toolset_pydantic_ai import SQLDatabaseDeps


@pytest_asyncio.fixture
async def writable_db() -> SQLDatabaseDeps:
    """Create a file-based writable SQLite database.

    Uses a temp file instead of :memory: to ensure persistence can be tested.
    """
    # Clear adapter cache to ensure fresh connections
    _adapter_cache.clear()

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    config = SQLToolConfig(
        tool_name="soliplex_sql.tools.query",
        database_url=f"sqlite:///{db_path}",
        read_only=False,
        max_rows=100,
        query_timeout=30.0,
    )
    deps = config.create_deps()

    await deps.database.connect()

    # Create test table
    await deps.database.execute("""
        CREATE TABLE test_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            value INTEGER DEFAULT 0
        )
    """)

    # Insert initial data
    await deps.database.execute("""
        INSERT INTO test_items (name, value) VALUES
        ('initial_item', 100)
    """)

    yield deps

    await deps.database.close()

    # Cleanup temp file
    try:
        Path(db_path).unlink()
    except OSError:
        pass


@pytest_asyncio.fixture
async def writable_adapter(writable_db: SQLDatabaseDeps) -> SoliplexSQLAdapter:
    """Create writable adapter."""
    return SoliplexSQLAdapter(writable_db)


class TestInsertOperations:
    """Tests for INSERT operations."""

    async def test_insert_returns_success(
        self, writable_adapter: SoliplexSQLAdapter
    ) -> None:
        """INSERT should execute without error."""
        result = await writable_adapter.query(
            "INSERT INTO test_items (name, value) VALUES ('new_item', 42)"
        )

        # SQLite INSERT doesn't return rows, but shouldn't error
        assert result is not None

    async def test_insert_persists_data(
        self, writable_adapter: SoliplexSQLAdapter
    ) -> None:
        """INSERT should persist data that can be read back."""
        # Insert new record
        await writable_adapter.query(
            "INSERT INTO test_items (name, value) VALUES ('persisted_item', 999)"
        )

        # Query should find the new record
        result = await writable_adapter.query(
            "SELECT name, value FROM test_items WHERE name = 'persisted_item'"
        )

        assert result["row_count"] == 1, (
            f"Expected 1 row, got {result['row_count']}. "
            "INSERT may not have been committed."
        )
        assert result["rows"][0][0] == "persisted_item"
        assert result["rows"][0][1] == 999

    async def test_multiple_inserts_persist(
        self, writable_adapter: SoliplexSQLAdapter
    ) -> None:
        """Multiple INSERTs should all persist."""
        # Insert multiple records
        await writable_adapter.query(
            "INSERT INTO test_items (name, value) VALUES ('item_a', 1)"
        )
        await writable_adapter.query(
            "INSERT INTO test_items (name, value) VALUES ('item_b', 2)"
        )
        await writable_adapter.query(
            "INSERT INTO test_items (name, value) VALUES ('item_c', 3)"
        )

        # Count should include all new items (plus the initial one)
        result = await writable_adapter.query(
            "SELECT COUNT(*) FROM test_items"
        )

        # initial_item + item_a + item_b + item_c = 4
        assert result["rows"][0][0] == 4, (
            f"Expected 4 rows, got {result['rows'][0][0]}. "
            "INSERTs may not have been committed."
        )


class TestUpdateOperations:
    """Tests for UPDATE operations."""

    async def test_update_modifies_data(
        self, writable_adapter: SoliplexSQLAdapter
    ) -> None:
        """UPDATE should modify existing data."""
        # Update the initial item
        await writable_adapter.query(
            "UPDATE test_items SET value = 200 WHERE name = 'initial_item'"
        )

        # Verify the update persisted
        result = await writable_adapter.query(
            "SELECT value FROM test_items WHERE name = 'initial_item'"
        )

        assert result["row_count"] == 1
        assert result["rows"][0][0] == 200, (
            f"Expected value 200, got {result['rows'][0][0]}. "
            "UPDATE may not have been committed."
        )

    async def test_update_multiple_rows(
        self, writable_adapter: SoliplexSQLAdapter
    ) -> None:
        """UPDATE affecting multiple rows should persist all changes."""
        # Insert more items
        await writable_adapter.query(
            "INSERT INTO test_items (name, value) VALUES ('bulk_1', 10)"
        )
        await writable_adapter.query(
            "INSERT INTO test_items (name, value) VALUES ('bulk_2', 20)"
        )

        # Update all items with value < 50
        await writable_adapter.query(
            "UPDATE test_items SET value = value * 10 WHERE value < 50"
        )

        # Verify updates
        result = await writable_adapter.query(
            "SELECT name, value FROM test_items WHERE name LIKE 'bulk_%' ORDER BY name"
        )

        assert result["row_count"] == 2
        assert result["rows"][0][1] == 100  # bulk_1: 10 * 10
        assert result["rows"][1][1] == 200  # bulk_2: 20 * 10


class TestDeleteOperations:
    """Tests for DELETE operations."""

    async def test_delete_removes_data(
        self, writable_adapter: SoliplexSQLAdapter
    ) -> None:
        """DELETE should remove data permanently."""
        # Insert item to delete
        await writable_adapter.query(
            "INSERT INTO test_items (name, value) VALUES ('to_delete', 0)"
        )

        # Verify it exists
        result = await writable_adapter.query(
            "SELECT COUNT(*) FROM test_items WHERE name = 'to_delete'"
        )
        assert result["rows"][0][0] == 1

        # Delete it
        await writable_adapter.query(
            "DELETE FROM test_items WHERE name = 'to_delete'"
        )

        # Verify it's gone
        result = await writable_adapter.query(
            "SELECT COUNT(*) FROM test_items WHERE name = 'to_delete'"
        )

        assert result["rows"][0][0] == 0, (
            "Expected 0 rows after DELETE. "
            "DELETE may not have been committed."
        )

    async def test_delete_with_condition(
        self, writable_adapter: SoliplexSQLAdapter
    ) -> None:
        """DELETE with WHERE should only remove matching rows."""
        # Insert items
        await writable_adapter.query(
            "INSERT INTO test_items (name, value) VALUES ('keep_me', 100)"
        )
        await writable_adapter.query(
            "INSERT INTO test_items (name, value) VALUES ('delete_me', 0)"
        )

        # Delete only low-value items
        await writable_adapter.query(
            "DELETE FROM test_items WHERE value < 50"
        )

        # Verify selective deletion
        result = await writable_adapter.query(
            "SELECT name FROM test_items ORDER BY name"
        )

        names = [row[0] for row in result["rows"]]
        assert "delete_me" not in names, "Item that should be deleted still exists"
        assert "keep_me" in names, "Item that should be kept was deleted"


class TestTransactionBehavior:
    """Tests verifying transaction commit behavior."""

    async def test_insert_visible_in_same_session(
        self, writable_adapter: SoliplexSQLAdapter
    ) -> None:
        """INSERTed data should be visible in the same session."""
        # Insert
        await writable_adapter.query(
            "INSERT INTO test_items (name, value) VALUES ('session_test', 555)"
        )

        # Immediately query
        result = await writable_adapter.query(
            "SELECT value FROM test_items WHERE name = 'session_test'"
        )

        assert result["row_count"] == 1
        assert result["rows"][0][0] == 555

    async def test_insert_visible_after_other_operations(
        self, writable_adapter: SoliplexSQLAdapter
    ) -> None:
        """INSERTed data should survive interleaved read operations."""
        # Insert
        await writable_adapter.query(
            "INSERT INTO test_items (name, value) VALUES ('survive_test', 777)"
        )

        # Do some read operations
        await writable_adapter.query("SELECT * FROM test_items")
        tables = await writable_adapter.list_tables()
        await writable_adapter.query("SELECT COUNT(*) FROM test_items")

        # Original insert should still be there
        result = await writable_adapter.query(
            "SELECT value FROM test_items WHERE name = 'survive_test'"
        )

        assert result["row_count"] == 1, (
            "INSERT was lost after interleaved read operations. "
            "Possible uncommitted transaction issue."
        )


class TestWriteWithFreshConnection:
    """Tests that verify writes persist across connection boundaries."""

    async def test_write_persists_across_adapters(self) -> None:
        """Data written through one adapter should be readable from another.

        This test creates two separate adapters to the same database file
        and verifies that writes from adapter1 are visible to adapter2.
        This is the definitive test for commit behavior.

        IMPORTANT: Uses the SoliplexSQLAdapter (not raw database) to ensure
        the commit workaround is applied.
        """
        _adapter_cache.clear()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # Create adapter 1 and write data
            config1 = SQLToolConfig(
                tool_name="soliplex_sql.tools.query",
                database_url=f"sqlite:///{db_path}",
                read_only=False,
                max_rows=100,
            )
            deps1 = config1.create_deps()
            await deps1.database.connect()
            adapter1 = SoliplexSQLAdapter(deps1)

            # Create table and insert data THROUGH THE ADAPTER
            # This ensures our commit workaround is applied
            await adapter1.query("""
                CREATE TABLE persistence_test (
                    id INTEGER PRIMARY KEY,
                    data TEXT
                )
            """)
            await adapter1.query("""
                INSERT INTO persistence_test (data) VALUES ('from_adapter_1')
            """)

            # Close adapter 1
            await deps1.database.close()

            # Clear cache to force new connection
            _adapter_cache.clear()

            # Create adapter 2 and try to read
            config2 = SQLToolConfig(
                tool_name="soliplex_sql.tools.query",
                database_url=f"sqlite:///{db_path}",
                read_only=True,  # Read-only to ensure we're just reading
                max_rows=100,
            )
            deps2 = config2.create_deps()
            adapter2 = SoliplexSQLAdapter(deps2)
            await deps2.database.connect()

            # This should find the data if commits worked
            result = await adapter2.query(
                "SELECT data FROM persistence_test"
            )

            await deps2.database.close()

            assert result["row_count"] == 1, (
                f"Expected 1 row from cross-adapter read, got {result['row_count']}. "
                "Write operations are NOT being committed to disk. "
                "The adapter's _commit_if_needed() may not be working."
            )
            assert result["rows"][0][0] == "from_adapter_1"

        finally:
            try:
                Path(db_path).unlink()
            except OSError:
                pass
