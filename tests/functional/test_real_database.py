"""Integration tests against real SQLite database.

These tests verify actual SQL execution, not mocked behavior.
They catch real SQL dialect issues and connection problems.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from soliplex_sql.adapter import SoliplexSQLAdapter
from soliplex_sql.exceptions import QueryExecutionError

if TYPE_CHECKING:
    pass


class TestListTables:
    """Tests for list_tables with real database."""

    async def test_returns_created_tables(
        self, adapter: SoliplexSQLAdapter
    ) -> None:
        """Should list tables created in the database."""
        tables = await adapter.list_tables()

        assert "users" in tables
        assert "posts" in tables

    async def test_returns_list_type(
        self, adapter: SoliplexSQLAdapter
    ) -> None:
        """Should return a list of strings."""
        tables = await adapter.list_tables()

        assert isinstance(tables, list)
        assert all(isinstance(t, str) for t in tables)


class TestGetSchema:
    """Tests for get_schema with real database."""

    async def test_returns_schema_dict(
        self, adapter: SoliplexSQLAdapter
    ) -> None:
        """Should return schema as dictionary."""
        schema = await adapter.get_schema()

        assert "tables" in schema
        assert isinstance(schema["tables"], list)

    async def test_schema_includes_users_table(
        self, adapter: SoliplexSQLAdapter
    ) -> None:
        """Should include users table in schema."""
        schema = await adapter.get_schema()

        table_names = [t["name"] for t in schema["tables"]]
        assert "users" in table_names

    async def test_schema_includes_column_info(
        self, adapter: SoliplexSQLAdapter
    ) -> None:
        """Should include column information."""
        schema = await adapter.get_schema()

        users_table = next(t for t in schema["tables"] if t["name"] == "users")
        column_names = [c["name"] for c in users_table["columns"]]

        assert "id" in column_names
        assert "name" in column_names
        assert "email" in column_names


class TestDescribeTable:
    """Tests for describe_table with real database."""

    async def test_describe_existing_table(
        self, adapter: SoliplexSQLAdapter
    ) -> None:
        """Should describe an existing table."""
        result = await adapter.describe_table("users")

        assert result is not None
        assert result["name"] == "users"
        assert "columns" in result

    async def test_describe_includes_column_details(
        self, adapter: SoliplexSQLAdapter
    ) -> None:
        """Should include detailed column info."""
        result = await adapter.describe_table("users")

        columns = result["columns"]
        id_col = next(c for c in columns if c["name"] == "id")

        assert "data_type" in id_col
        assert "nullable" in id_col

    async def test_describe_nonexistent_table(
        self, adapter: SoliplexSQLAdapter
    ) -> None:
        """Should return None for nonexistent table."""
        result = await adapter.describe_table("nonexistent")

        assert result is None


class TestQuery:
    """Tests for query with real database."""

    async def test_simple_select(self, adapter: SoliplexSQLAdapter) -> None:
        """Should execute simple SELECT query."""
        result = await adapter.query("SELECT * FROM users")

        assert "columns" in result
        assert "rows" in result
        assert "row_count" in result

    async def test_query_returns_data(
        self, adapter: SoliplexSQLAdapter
    ) -> None:
        """Should return actual data from database."""
        result = await adapter.query("SELECT name FROM users ORDER BY name")

        names = [row[0] for row in result["rows"]]
        assert "Alice" in names
        assert "Bob" in names
        assert "Charlie" in names

    async def test_query_with_where(self, adapter: SoliplexSQLAdapter) -> None:
        """Should filter results with WHERE clause."""
        result = await adapter.query(
            "SELECT name FROM users WHERE name = 'Alice'"
        )

        assert result["row_count"] == 1
        assert result["rows"][0][0] == "Alice"

    async def test_query_with_join(self, adapter: SoliplexSQLAdapter) -> None:
        """Should handle JOIN queries."""
        result = await adapter.query("""
            SELECT u.name, p.title
            FROM users u
            JOIN posts p ON u.id = p.user_id
            ORDER BY p.id
        """)

        assert result["row_count"] == 3

    async def test_query_respects_max_rows(
        self, adapter: SoliplexSQLAdapter
    ) -> None:
        """Should truncate results to max_rows."""
        result = await adapter.query(
            "SELECT * FROM users",
            max_rows=1,
        )

        assert result["row_count"] == 1
        assert result["truncated"] is True

    async def test_query_returns_columns(
        self, adapter: SoliplexSQLAdapter
    ) -> None:
        """Should return column names."""
        result = await adapter.query("SELECT id, name FROM users")

        assert "id" in result["columns"]
        assert "name" in result["columns"]


class TestExplainQuery:
    """Tests for explain_query with real database."""

    async def test_explain_returns_plan(
        self, adapter: SoliplexSQLAdapter
    ) -> None:
        """Should return query execution plan."""
        plan = await adapter.explain_query("SELECT * FROM users WHERE id = 1")

        assert isinstance(plan, str)
        assert len(plan) > 0


class TestSampleQuery:
    """Tests for sample_query with real database."""

    async def test_sample_query_limits_results(
        self, adapter: SoliplexSQLAdapter
    ) -> None:
        """Should limit results to sample size."""
        result = await adapter.sample_query(
            "SELECT * FROM users",
            limit=2,
        )

        assert result["row_count"] == 2

    async def test_sample_query_default_limit(
        self, adapter: SoliplexSQLAdapter
    ) -> None:
        """Should use default limit of 5."""
        result = await adapter.sample_query("SELECT * FROM users")

        # We have 3 users, should return all (< 5)
        assert result["row_count"] == 3


class TestReadOnlyMode:
    """Tests for read_only enforcement."""

    async def test_select_allowed_in_read_only(
        self, read_only_adapter: SoliplexSQLAdapter
    ) -> None:
        """SELECT should work in read-only mode."""
        result = await read_only_adapter.query("SELECT * FROM items")

        assert result["row_count"] == 2

    async def test_insert_blocked_in_read_only(
        self, read_only_adapter: SoliplexSQLAdapter
    ) -> None:
        """INSERT should be blocked in read-only mode."""
        with pytest.raises(QueryExecutionError, match="read-only"):
            await read_only_adapter.query(
                "INSERT INTO items (name) VALUES ('New')"
            )

    async def test_update_blocked_in_read_only(
        self, read_only_adapter: SoliplexSQLAdapter
    ) -> None:
        """UPDATE should be blocked in read-only mode."""
        with pytest.raises(QueryExecutionError, match="read-only"):
            await read_only_adapter.query(
                "UPDATE items SET name = 'Changed' WHERE id = 1"
            )

    async def test_delete_blocked_in_read_only(
        self, read_only_adapter: SoliplexSQLAdapter
    ) -> None:
        """DELETE should be blocked in read-only mode."""
        with pytest.raises(QueryExecutionError, match="read-only"):
            await read_only_adapter.query("DELETE FROM items WHERE id = 1")

    async def test_drop_blocked_in_read_only(
        self, read_only_adapter: SoliplexSQLAdapter
    ) -> None:
        """DROP should be blocked in read-only mode."""
        with pytest.raises(QueryExecutionError, match="read-only"):
            await read_only_adapter.query("DROP TABLE items")

    async def test_explain_allowed_in_read_only(
        self, read_only_adapter: SoliplexSQLAdapter
    ) -> None:
        """EXPLAIN should work in read-only mode."""
        plan = await read_only_adapter.explain_query("SELECT * FROM items")
        assert len(plan) > 0

    async def test_pragma_allowed_in_read_only(
        self, read_only_adapter: SoliplexSQLAdapter
    ) -> None:
        """PRAGMA should work in read-only mode."""
        result = await read_only_adapter.query("PRAGMA table_info(items)")
        assert result is not None

    async def test_cte_allowed_in_read_only(
        self, read_only_adapter: SoliplexSQLAdapter
    ) -> None:
        """WITH (CTE) queries should work in read-only mode."""
        result = await read_only_adapter.query("""
            WITH item_counts AS (
                SELECT COUNT(*) as cnt FROM items
            )
            SELECT * FROM item_counts
        """)
        assert result is not None
        assert result["row_count"] == 1
