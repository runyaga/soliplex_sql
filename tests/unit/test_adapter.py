"""Tests for adapter module."""

from __future__ import annotations

from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from soliplex_sql.adapter import SoliplexSQLAdapter, _split_statements
from soliplex_sql.exceptions import QueryExecutionError


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


class TestStatementSplitting:
    """Tests for _split_statements function."""

    def test_single_statement(self) -> None:
        """Single statement without semicolon."""
        result = _split_statements("SELECT * FROM users")
        assert result == ["SELECT * FROM users"]

    def test_single_statement_with_semicolon(self) -> None:
        """Single statement with trailing semicolon."""
        result = _split_statements("SELECT * FROM users;")
        assert result == ["SELECT * FROM users"]

    def test_multiple_statements(self) -> None:
        """Multiple statements separated by semicolons."""
        sql = "INSERT INTO users (name) VALUES ('a'); INSERT INTO users (name) VALUES ('b')"
        result = _split_statements(sql)
        assert result == [
            "INSERT INTO users (name) VALUES ('a')",
            "INSERT INTO users (name) VALUES ('b')",
        ]

    def test_semicolon_in_string_literal(self) -> None:
        """Semicolon inside string literal should not split."""
        sql = "INSERT INTO users (name) VALUES ('hello; world')"
        result = _split_statements(sql)
        assert result == ["INSERT INTO users (name) VALUES ('hello; world')"]

    def test_semicolon_in_double_quoted_string(self) -> None:
        """Semicolon inside double-quoted string should not split."""
        sql = 'SELECT "col;name" FROM users'
        result = _split_statements(sql)
        assert result == ['SELECT "col;name" FROM users']

    def test_escaped_quote_in_string(self) -> None:
        """Escaped quotes (doubled) should be handled."""
        sql = "INSERT INTO users (name) VALUES ('it''s a test')"
        result = _split_statements(sql)
        assert result == ["INSERT INTO users (name) VALUES ('it''s a test')"]

    def test_mixed_statements(self) -> None:
        """Mix of write and read statements."""
        sql = "INSERT INTO t (x) VALUES (1); SELECT * FROM t; UPDATE t SET x = 2"
        result = _split_statements(sql)
        assert result == [
            "INSERT INTO t (x) VALUES (1)",
            "SELECT * FROM t",
            "UPDATE t SET x = 2",
        ]

    def test_empty_string(self) -> None:
        """Empty string returns empty list."""
        assert _split_statements("") == []

    def test_whitespace_only(self) -> None:
        """Whitespace only returns empty list."""
        assert _split_statements("   \n\t  ") == []

    def test_multiple_semicolons(self) -> None:
        """Multiple consecutive semicolons should not create empty statements."""
        sql = "SELECT 1;; SELECT 2"
        result = _split_statements(sql)
        assert result == ["SELECT 1", "SELECT 2"]


class TestWriteQueryDetection:
    """Tests for _is_write_query method."""

    @pytest.fixture
    def adapter(self, mock_sql_deps: MagicMock) -> SoliplexSQLAdapter:
        """Create adapter with mock deps."""
        mock_sql_deps.read_only = False
        return SoliplexSQLAdapter(mock_sql_deps)

    @pytest.mark.parametrize(
        "query",
        [
            "INSERT INTO users (name) VALUES ('test')",
            "insert into users (name) values ('test')",
            "  INSERT INTO users (name) VALUES ('test')",
            "UPDATE users SET name = 'test'",
            "update users set name = 'test'",
            "DELETE FROM users WHERE id = 1",
            "delete from users where id = 1",
            "CREATE TABLE test (id INT)",
            "DROP TABLE test",
            "ALTER TABLE users ADD COLUMN age INT",
            "REPLACE INTO users (id, name) VALUES (1, 'test')",
            "TRUNCATE TABLE users",
        ],
    )
    def test_detects_write_queries(
        self, adapter: SoliplexSQLAdapter, query: str
    ) -> None:
        """Should identify write queries."""
        assert adapter._is_write_query(query) is True

    @pytest.mark.parametrize(
        "query",
        [
            "SELECT * FROM users",
            "select * from users",
            "  SELECT * FROM users",
            "EXPLAIN SELECT * FROM users",
            "PRAGMA table_info(users)",
            "SHOW TABLES",
            "DESCRIBE users",
            "WITH cte AS (SELECT 1) SELECT * FROM cte",
        ],
    )
    def test_detects_read_queries(
        self, adapter: SoliplexSQLAdapter, query: str
    ) -> None:
        """Should identify read-only queries."""
        assert adapter._is_write_query(query) is False


class TestWriteCommit:
    """Tests for write operation commit behavior."""

    @pytest.fixture
    def writable_deps(self, mock_database: MagicMock) -> MagicMock:
        """Create mock deps with write access."""
        deps = MagicMock()
        deps.database = mock_database
        deps.read_only = False
        deps.max_rows = 100
        deps.query_timeout = 30.0
        return deps

    async def test_commit_called_on_insert(
        self, writable_deps: MagicMock
    ) -> None:
        """INSERT should trigger commit."""
        mock_connection = AsyncMock()
        writable_deps.database._connection = mock_connection
        writable_deps.database.execute = AsyncMock(
            return_value=MagicMock(
                columns=[], rows=[], execution_time_ms=1.0
            )
        )

        adapter = SoliplexSQLAdapter(writable_deps)
        await adapter.query("INSERT INTO users (name) VALUES ('test')")

        mock_connection.commit.assert_called_once()

    async def test_commit_called_on_update(
        self, writable_deps: MagicMock
    ) -> None:
        """UPDATE should trigger commit."""
        mock_connection = AsyncMock()
        writable_deps.database._connection = mock_connection
        writable_deps.database.execute = AsyncMock(
            return_value=MagicMock(
                columns=[], rows=[], execution_time_ms=1.0
            )
        )

        adapter = SoliplexSQLAdapter(writable_deps)
        await adapter.query("UPDATE users SET name = 'test'")

        mock_connection.commit.assert_called_once()

    async def test_commit_called_on_delete(
        self, writable_deps: MagicMock
    ) -> None:
        """DELETE should trigger commit."""
        mock_connection = AsyncMock()
        writable_deps.database._connection = mock_connection
        writable_deps.database.execute = AsyncMock(
            return_value=MagicMock(
                columns=[], rows=[], execution_time_ms=1.0
            )
        )

        adapter = SoliplexSQLAdapter(writable_deps)
        await adapter.query("DELETE FROM users WHERE id = 1")

        mock_connection.commit.assert_called_once()

    async def test_no_commit_on_select(
        self, writable_deps: MagicMock
    ) -> None:
        """SELECT should not trigger commit."""
        mock_connection = AsyncMock()
        writable_deps.database._connection = mock_connection
        writable_deps.database.execute = AsyncMock(
            return_value=MagicMock(
                columns=["id"], rows=[(1,)], execution_time_ms=1.0
            )
        )

        adapter = SoliplexSQLAdapter(writable_deps)
        await adapter.query("SELECT * FROM users")

        mock_connection.commit.assert_not_called()

    async def test_commit_handles_missing_connection(
        self, writable_deps: MagicMock
    ) -> None:
        """Should handle case where _connection is not available."""
        # Remove _connection attribute
        del writable_deps.database._connection
        writable_deps.database.execute = AsyncMock(
            return_value=MagicMock(
                columns=[], rows=[], execution_time_ms=1.0
            )
        )

        adapter = SoliplexSQLAdapter(writable_deps)
        # Should not raise
        await adapter.query("INSERT INTO users (name) VALUES ('test')")

    async def test_commit_handles_no_commit_method(
        self, writable_deps: MagicMock
    ) -> None:
        """Should handle backends without commit method."""
        mock_connection = MagicMock()
        # MagicMock without commit attribute (will have it by default)
        # Explicitly delete it
        del mock_connection.commit
        writable_deps.database._connection = mock_connection
        writable_deps.database.execute = AsyncMock(
            return_value=MagicMock(
                columns=[], rows=[], execution_time_ms=1.0
            )
        )

        adapter = SoliplexSQLAdapter(writable_deps)
        # Should not raise
        await adapter.query("INSERT INTO users (name) VALUES ('test')")


class TestReadOnlyEnforcement:
    """Tests for read-only mode enforcement."""

    @pytest.fixture
    def readonly_deps(self, mock_database: MagicMock) -> MagicMock:
        """Create mock deps in read-only mode."""
        deps = MagicMock()
        deps.database = mock_database
        deps.read_only = True
        deps.max_rows = 100
        deps.query_timeout = 30.0
        return deps

    async def test_insert_blocked_in_readonly(
        self, readonly_deps: MagicMock
    ) -> None:
        """INSERT should be blocked in read-only mode."""
        adapter = SoliplexSQLAdapter(readonly_deps)

        with pytest.raises(QueryExecutionError, match="read-only"):
            await adapter.query("INSERT INTO users (name) VALUES ('test')")

    async def test_update_blocked_in_readonly(
        self, readonly_deps: MagicMock
    ) -> None:
        """UPDATE should be blocked in read-only mode."""
        adapter = SoliplexSQLAdapter(readonly_deps)

        with pytest.raises(QueryExecutionError, match="read-only"):
            await adapter.query("UPDATE users SET name = 'test'")

    async def test_delete_blocked_in_readonly(
        self, readonly_deps: MagicMock
    ) -> None:
        """DELETE should be blocked in read-only mode."""
        adapter = SoliplexSQLAdapter(readonly_deps)

        with pytest.raises(QueryExecutionError, match="read-only"):
            await adapter.query("DELETE FROM users")

    async def test_select_allowed_in_readonly(
        self, readonly_deps: MagicMock
    ) -> None:
        """SELECT should work in read-only mode."""
        readonly_deps.database.execute = AsyncMock(
            return_value=MagicMock(
                columns=["id"], rows=[(1,)], execution_time_ms=1.0
            )
        )
        adapter = SoliplexSQLAdapter(readonly_deps)

        result = await adapter.query("SELECT * FROM users")

        assert result["row_count"] == 1
