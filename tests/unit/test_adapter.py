"""Tests for adapter module."""

from __future__ import annotations

from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from soliplex_sql.adapter import SoliplexSQLAdapter


class TestSoliplexSQLAdapter:
    """Tests for SoliplexSQLAdapter."""

    @pytest.fixture
    def adapter(self, mock_sql_deps: MagicMock) -> SoliplexSQLAdapter:
        """Create adapter with mock deps."""
        return SoliplexSQLAdapter(mock_sql_deps)

    def test_init(self, adapter: SoliplexSQLAdapter) -> None:
        """Should initialize with sql_deps."""
        assert adapter.database is not None

    def test_read_only_property(self, adapter: SoliplexSQLAdapter) -> None:
        """Should expose read_only setting."""
        assert adapter.read_only is True

    def test_max_rows_property(self, adapter: SoliplexSQLAdapter) -> None:
        """Should expose max_rows setting."""
        assert adapter.max_rows == 100

    async def test_list_tables(
        self,
        mock_sql_deps: MagicMock,
    ) -> None:
        """Should list tables from database."""
        mock_sql_deps.database.get_tables = AsyncMock(
            return_value=["users", "posts"]
        )
        adapter = SoliplexSQLAdapter(mock_sql_deps)

        tables = await adapter.list_tables()

        assert tables == ["users", "posts"]
        mock_sql_deps.database.get_tables.assert_called_once()

    async def test_get_schema(
        self,
        mock_sql_deps: MagicMock,
    ) -> None:
        """Should get schema from database."""
        mock_table = MagicMock()
        mock_table.name = "users"
        mock_table.columns = []
        mock_table.row_count = 10

        mock_schema = MagicMock()
        mock_schema.tables = [mock_table]

        mock_sql_deps.database.get_schema = AsyncMock(return_value=mock_schema)
        adapter = SoliplexSQLAdapter(mock_sql_deps)

        schema = await adapter.get_schema()

        assert "tables" in schema
        assert len(schema["tables"]) == 1
        assert schema["tables"][0]["name"] == "users"

    async def test_describe_table(
        self,
        mock_sql_deps: MagicMock,
    ) -> None:
        """Should describe table from database."""
        mock_column = MagicMock()
        mock_column.name = "id"
        mock_column.data_type = "INTEGER"
        mock_column.nullable = False
        mock_column.default = None
        mock_column.is_primary_key = True

        mock_table = MagicMock()
        mock_table.name = "users"
        mock_table.columns = [mock_column]
        mock_table.row_count = 10
        mock_table.primary_key = ["id"]
        mock_table.foreign_keys = None

        mock_sql_deps.database.get_table_info = AsyncMock(
            return_value=mock_table
        )
        adapter = SoliplexSQLAdapter(mock_sql_deps)

        info = await adapter.describe_table("users")

        assert info is not None
        assert info["name"] == "users"
        assert len(info["columns"]) == 1

    async def test_describe_table_not_found(
        self,
        mock_sql_deps: MagicMock,
    ) -> None:
        """Should return None for non-existent table."""
        mock_sql_deps.database.get_table_info = AsyncMock(return_value=None)
        adapter = SoliplexSQLAdapter(mock_sql_deps)

        info = await adapter.describe_table("nonexistent")

        assert info is None

    async def test_query(
        self,
        mock_sql_deps: MagicMock,
    ) -> None:
        """Should execute query and return results."""
        mock_result = MagicMock()
        mock_result.columns = ["id", "name"]
        mock_result.rows = [(1, "Alice"), (2, "Bob")]
        mock_result.execution_time_ms = 5.0

        mock_sql_deps.database.execute = AsyncMock(return_value=mock_result)
        adapter = SoliplexSQLAdapter(mock_sql_deps)

        result = await adapter.query("SELECT * FROM users")

        assert result["columns"] == ["id", "name"]
        assert result["row_count"] == 2
        assert result["truncated"] is False

    async def test_query_truncates_results(
        self,
        mock_sql_deps: MagicMock,
    ) -> None:
        """Should truncate results to max_rows."""
        mock_result = MagicMock()
        mock_result.columns = ["id"]
        mock_result.rows = [(i,) for i in range(200)]  # 200 rows
        mock_result.execution_time_ms = 10.0

        mock_sql_deps.database.execute = AsyncMock(return_value=mock_result)
        mock_sql_deps.max_rows = 100
        adapter = SoliplexSQLAdapter(mock_sql_deps)

        result = await adapter.query("SELECT * FROM big_table")

        assert result["row_count"] == 100
        assert result["truncated"] is True

    async def test_explain_query(
        self,
        mock_sql_deps: MagicMock,
    ) -> None:
        """Should return query execution plan."""
        mock_sql_deps.database.explain = AsyncMock(
            return_value="SCAN TABLE users"
        )
        adapter = SoliplexSQLAdapter(mock_sql_deps)

        plan = await adapter.explain_query("SELECT * FROM users")

        assert "SCAN" in plan

    async def test_sample_query(
        self,
        mock_sql_deps: MagicMock,
    ) -> None:
        """Should execute sample query with limit."""
        mock_result = MagicMock()
        mock_result.columns = ["id"]
        mock_result.rows = [(1,), (2,), (3,)]
        mock_result.execution_time_ms = 1.0

        mock_sql_deps.database.execute = AsyncMock(return_value=mock_result)
        adapter = SoliplexSQLAdapter(mock_sql_deps)

        result = await adapter.sample_query("SELECT * FROM users", limit=5)

        assert result["row_count"] == 3

    async def test_close(
        self,
        mock_sql_deps: MagicMock,
    ) -> None:
        """Should close database connection."""
        mock_sql_deps.database.close = AsyncMock()
        adapter = SoliplexSQLAdapter(mock_sql_deps)

        await adapter.close()

        mock_sql_deps.database.close.assert_called_once()
