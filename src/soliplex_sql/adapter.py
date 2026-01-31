"""Core adapter bridging sql-toolset-pydantic-ai with Soliplex.

This adapter calls the upstream database backend directly rather than
using create_database_toolset(). This avoids unnecessary FunctionToolset
overhead and gives full control over query execution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from soliplex_sql.exceptions import QueryExecutionError

if TYPE_CHECKING:
    from sql_toolset_pydantic_ai import SQLDatabaseDeps

# SQL statements allowed in read-only mode
# WITH is included for Common Table Expressions (CTEs)
_READONLY_PREFIXES = (
    "SELECT", "EXPLAIN", "PRAGMA", "SHOW", "DESCRIBE", "WITH"
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

    async def query(
        self,
        sql_query: str,
        max_rows: int | None = None,
    ) -> dict[str, Any]:
        """Execute a SQL query and return results.

        Args:
            sql_query: SQL query to execute
            max_rows: Maximum rows to return

        Returns:
            Query results with columns, rows, metadata

        Raises:
            QueryExecutionError: If mutation attempted in read-only mode
        """
        # Enforce read-only mode
        self._check_read_only(sql_query)

        result = await self._sql_deps.database.execute(sql_query)

        limit = max_rows or self._sql_deps.max_rows
        rows = result.rows[:limit]
        truncated = len(result.rows) > limit

        return {
            "columns": result.columns,
            "rows": [list(row) for row in rows],
            "row_count": len(rows),
            "truncated": truncated,
            "execution_time_ms": result.execution_time_ms,
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
