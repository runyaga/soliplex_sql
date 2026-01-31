"""Tests for tool wrapper functions in tools.py.

These tests verify the exported tool functions work correctly
with RunContext and database operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
import pytest_asyncio

from soliplex_sql.config import SQLToolConfig
from soliplex_sql.tools import _adapter_cache
from soliplex_sql.tools import describe_table
from soliplex_sql.tools import explain_query
from soliplex_sql.tools import get_schema
from soliplex_sql.tools import list_tables
from soliplex_sql.tools import query
from soliplex_sql.tools import sample_query

if TYPE_CHECKING:
    from sql_toolset_pydantic_ai import SQLDatabaseDeps


@pytest_asyncio.fixture
async def tool_test_db() -> SQLDatabaseDeps:
    """Create in-memory SQLite for tool function tests.

    Returns SQLDatabaseDeps and registers in cache via config.
    """
    from sql_toolset_pydantic_ai import SQLDatabaseDeps
    from sql_toolset_pydantic_ai import SQLiteDatabase

    backend = SQLiteDatabase(":memory:", read_only=False)
    await backend.connect()

    await backend.execute("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL
        )
    """)

    await backend.execute("""
        INSERT INTO products (name, price) VALUES
        ('Widget', 9.99),
        ('Gadget', 19.99),
        ('Gizmo', 29.99)
    """)

    deps = SQLDatabaseDeps(
        database=backend,
        read_only=False,
        max_rows=100,
        query_timeout=30.0,
    )

    yield deps

    await backend.close()


@pytest.fixture
def mock_ctx_with_db(tool_test_db: SQLDatabaseDeps) -> MagicMock:
    """Create mock RunContext with SQL config pointing to test db.

    Note: This directly caches the adapter to avoid re-creating DB.
    """
    from soliplex_sql.adapter import SoliplexSQLAdapter

    # Create config matching cached key
    config = SQLToolConfig(
        tool_name="soliplex_sql.tools.query",
        database_url="sqlite:///:memory:_test",
        read_only=False,
        max_rows=100,
    )

    # Create adapter and cache it
    adapter = SoliplexSQLAdapter(tool_test_db)
    cache_key = (config.database_url, config.read_only, config.max_rows)
    _adapter_cache[cache_key] = adapter

    # Create mock context
    ctx = MagicMock()
    ctx.deps = MagicMock()
    ctx.deps.tool_configs = {"query": config}

    return ctx


class TestListTablesTool:
    """Tests for list_tables tool function."""

    async def test_list_tables_returns_tables(
        self,
        mock_ctx_with_db: MagicMock,
    ) -> None:
        """list_tables tool should return table names."""
        result = await list_tables(mock_ctx_with_db)

        assert isinstance(result, list)
        assert "products" in result


class TestGetSchemaTool:
    """Tests for get_schema tool function."""

    async def test_get_schema_returns_dict(
        self,
        mock_ctx_with_db: MagicMock,
    ) -> None:
        """get_schema tool should return schema dict."""
        result = await get_schema(mock_ctx_with_db)

        assert isinstance(result, dict)
        assert "tables" in result


class TestDescribeTableTool:
    """Tests for describe_table tool function."""

    async def test_describe_table_returns_info(
        self,
        mock_ctx_with_db: MagicMock,
    ) -> None:
        """describe_table tool should return table info."""
        result = await describe_table(mock_ctx_with_db, "products")

        assert result is not None
        assert result["name"] == "products"
        assert "columns" in result

    async def test_describe_table_nonexistent(
        self,
        mock_ctx_with_db: MagicMock,
    ) -> None:
        """describe_table tool should return None for nonexistent."""
        result = await describe_table(mock_ctx_with_db, "nonexistent")

        assert result is None


class TestQueryTool:
    """Tests for query tool function."""

    async def test_query_returns_results(
        self,
        mock_ctx_with_db: MagicMock,
    ) -> None:
        """query tool should execute and return results."""
        result = await query(
            mock_ctx_with_db,
            "SELECT name, price FROM products ORDER BY name",
        )

        assert "columns" in result
        assert "rows" in result
        assert result["row_count"] == 3

    async def test_query_with_max_rows(
        self,
        mock_ctx_with_db: MagicMock,
    ) -> None:
        """query tool should respect max_rows parameter."""
        result = await query(
            mock_ctx_with_db,
            "SELECT * FROM products",
            max_rows=1,
        )

        assert result["row_count"] == 1
        assert result["truncated"] is True


class TestExplainQueryTool:
    """Tests for explain_query tool function."""

    async def test_explain_query_returns_plan(
        self,
        mock_ctx_with_db: MagicMock,
    ) -> None:
        """explain_query tool should return execution plan."""
        result = await explain_query(
            mock_ctx_with_db,
            "SELECT * FROM products WHERE id = 1",
        )

        assert isinstance(result, str)
        assert len(result) > 0


class TestSampleQueryTool:
    """Tests for sample_query tool function."""

    async def test_sample_query_limits_results(
        self,
        mock_ctx_with_db: MagicMock,
    ) -> None:
        """sample_query tool should limit results."""
        result = await sample_query(
            mock_ctx_with_db,
            "SELECT * FROM products",
            limit=2,
        )

        assert result["row_count"] == 2

    async def test_sample_query_default_limit(
        self,
        mock_ctx_with_db: MagicMock,
    ) -> None:
        """sample_query tool should use default limit."""
        result = await sample_query(
            mock_ctx_with_db,
            "SELECT * FROM products",
        )

        # We have 3 products, default limit is 5
        assert result["row_count"] == 3
