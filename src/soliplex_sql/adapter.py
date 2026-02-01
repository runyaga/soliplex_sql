"""Core adapter bridging sql-toolset-pydantic-ai with Soliplex.

This adapter calls the upstream database backend directly rather than
using create_database_toolset(). This avoids unnecessary FunctionToolset
overhead and gives full control over query execution.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from typing import Any

from soliplex_sql.exceptions import QueryExecutionError

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from sql_toolset_pydantic_ai import SQLDatabaseDeps


def _split_statements(sql: str) -> list[str]:
    """Split SQL into individual statements.

    Handles semicolons inside string literals by using a simple state machine.
    This allows multi-statement queries like "INSERT...; INSERT...;" to work
    with SQLite which only allows one statement per execute().

    Args:
        sql: SQL string potentially containing multiple statements

    Returns:
        List of individual SQL statements (empty strings filtered out)
    """
    statements = []
    current = []
    in_string = False
    string_char = None
    i = 0

    while i < len(sql):
        char = sql[i]

        # Handle string literals
        if char in ("'", '"') and not in_string:
            in_string = True
            string_char = char
            current.append(char)
        elif char == string_char and in_string:
            # Check for escaped quote (doubled)
            if i + 1 < len(sql) and sql[i + 1] == string_char:
                current.append(char)
                current.append(sql[i + 1])
                i += 1
            else:
                in_string = False
                string_char = None
                current.append(char)
        elif char == ";" and not in_string:
            # End of statement
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
        else:
            current.append(char)

        i += 1

    # Don't forget the last statement (may not end with semicolon)
    stmt = "".join(current).strip()
    if stmt:
        statements.append(stmt)

    return statements


# SQL statements allowed in read-only mode
# WITH is included for Common Table Expressions (CTEs)
_READONLY_PREFIXES = (
    "SELECT",
    "EXPLAIN",
    "PRAGMA",
    "SHOW",
    "DESCRIBE",
    "WITH",
)

# Write operations that require commit
# MERGE and CALL are for PostgreSQL (not supported in SQLite)
_WRITE_PREFIXES = (
    "INSERT",
    "UPDATE",
    "DELETE",
    "CREATE",
    "DROP",
    "ALTER",
    "REPLACE",
    "TRUNCATE",
    "MERGE",  # PostgreSQL 15+
    "CALL",  # PostgreSQL 11+ (stored procedures)
)


class SoliplexSQLAdapter:
    """Adapter wrapping sql-toolset-pydantic-ai for Soliplex.

    Provides:
    - Integration with Soliplex AgentDependencies
    - Soliplex ToolConfig compatibility
    - Read-only mode enforcement

    Calls backend directly, not via create_database_toolset().
    """

    def __init__(self, sql_deps: SQLDatabaseDeps) -> None:
        """Initialize adapter with SQL dependencies.

        Args:
            sql_deps: Configured SQLDatabaseDeps from upstream library
        """
        self._sql_deps = sql_deps

    @property
    def database(self) -> Any:
        """Return the database backend."""
        return self._sql_deps.database

    @property
    def read_only(self) -> bool:
        """Return read_only setting."""
        return self._sql_deps.read_only

    @property
    def max_rows(self) -> int:
        """Return max_rows setting."""
        return self._sql_deps.max_rows

    async def list_tables(self) -> list[str]:
        """List all tables in the database.

        Returns:
            List of table names
        """
        return await self._sql_deps.database.get_tables()

    async def get_schema(self) -> dict[str, Any]:
        """Get database schema overview.

        Returns:
            Schema information with tables, columns, row counts
        """
        schema = await self._sql_deps.database.get_schema()

        return {
            "tables": [
                {
                    "name": t.name,
                    "columns": [
                        {
                            "name": c.name,
                            "data_type": c.data_type,
                            "nullable": c.nullable,
                        }
                        for c in t.columns
                    ],
                    "row_count": t.row_count,
                }
                for t in schema.tables
            ],
        }

    async def describe_table(
        self,
        table_name: str,
    ) -> dict[str, Any] | None:
        """Get detailed information about a specific table.

        Args:
            table_name: Name of the table to describe

        Returns:
            Table information or None if table not found
        """
        table_info = await self._sql_deps.database.get_table_info(table_name)

        if table_info is None:
            return None

        return {
            "name": table_info.name,
            "columns": [
                {
                    "name": c.name,
                    "data_type": c.data_type,
                    "nullable": c.nullable,
                    "default": c.default,
                    "is_primary_key": c.is_primary_key,
                }
                for c in table_info.columns
            ],
            "row_count": table_info.row_count,
            "primary_key": table_info.primary_key,
            "foreign_keys": (
                [
                    {
                        "column": fk.column,
                        "references_table": fk.references_table,
                        "references_column": fk.references_column,
                    }
                    for fk in table_info.foreign_keys
                ]
                if table_info.foreign_keys
                else None
            ),
        }

    def _check_read_only(self, sql_query: str) -> None:
        """Check if query is allowed in read-only mode.

        Args:
            sql_query: SQL query to check

        Raises:
            QueryExecutionError: If mutation attempted in read-only mode
        """
        if not self.read_only:
            return

        normalized = sql_query.strip().upper()
        if not normalized.startswith(_READONLY_PREFIXES):
            msg = "Database is in read-only mode. "
            msg += "Only SELECT, EXPLAIN, PRAGMA, SHOW, DESCRIBE allowed."
            raise QueryExecutionError(msg)

    def _is_write_query(self, sql_query: str) -> bool:
        """Check if query modifies the database.

        Args:
            sql_query: SQL query to check

        Returns:
            True if query is a write operation
        """
        normalized = sql_query.strip().upper()
        return normalized.startswith(_WRITE_PREFIXES)

    async def _commit_if_needed(self, sql_query: str) -> None:
        """Commit transaction if query was a write operation.

        The upstream sql-toolset-pydantic-ai library doesn't commit after
        write operations, causing changes to be lost. This method works
        around that by accessing the internal connection.

        Args:
            sql_query: SQL query that was executed
        """
        if not self._is_write_query(sql_query):
            return

        # Access internal connection to commit
        # Works with SQLiteDatabase (aiosqlite) and PostgreSQLDatabase
        database = self._sql_deps.database
        connection = getattr(database, "_connection", None)

        if connection is None:
            logger.warning(
                "Could not access _connection to commit. "
                "Write may not persist if upstream library changed."
            )
            return

        # aiosqlite connection has commit()
        if hasattr(connection, "commit"):
            await connection.commit()

    async def query(
        self,
        sql_query: str,
        max_rows: int | None = None,
    ) -> dict[str, Any]:
        """Execute a SQL query and return results.

        Supports multiple statements separated by semicolons.
        Each statement is executed separately (SQLite requirement).
        Returns combined results from all statements.

        Args:
            sql_query: SQL query to execute (may contain multiple statements)
            max_rows: Maximum rows to return

        Returns:
            Query results with columns, rows, metadata

        Raises:
            QueryExecutionError: If mutation attempted in read-only mode
        """
        # Split into individual statements
        statements = _split_statements(sql_query)

        if not statements:
            return {
                "columns": [],
                "rows": [],
                "row_count": 0,
                "truncated": False,
                "execution_time_ms": 0.0,
            }

        # Execute each statement
        all_columns: list[str] = []
        all_rows: list[list[Any]] = []
        total_time = 0.0
        had_write = False

        for stmt in statements:
            # Enforce read-only mode for each statement
            self._check_read_only(stmt)

            result = await self._sql_deps.database.execute(stmt)
            total_time += result.execution_time_ms

            # Track if any statement was a write
            if self._is_write_query(stmt):
                had_write = True

            # Collect results (use columns from last SELECT-like statement)
            if result.columns:
                all_columns = result.columns
                all_rows.extend([list(row) for row in result.rows])

        # Commit if any statement was a write
        if had_write:
            await self._commit_if_needed(statements[0])

        limit = max_rows or self._sql_deps.max_rows
        rows = all_rows[:limit]
        truncated = len(all_rows) > limit

        return {
            "columns": all_columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": truncated,
            "execution_time_ms": total_time,
        }

    async def explain_query(self, sql_query: str) -> str:
        """Get the execution plan for a SQL query.

        Args:
            sql_query: SQL query to analyze

        Returns:
            Query execution plan as string
        """
        return await self._sql_deps.database.explain(sql_query)

    async def sample_query(
        self,
        sql_query: str,
        limit: int = 5,
    ) -> dict[str, Any]:
        """Execute a sample query for quick data exploration.

        Args:
            sql_query: SQL query to execute
            limit: Maximum rows (default: 5)

        Returns:
            Sample query results
        """
        return await self.query(sql_query, max_rows=limit)

    async def close(self) -> None:
        """Close the database connection."""
        await self._sql_deps.database.close()
