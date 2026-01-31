"""Core adapter bridging sql-toolset-pydantic-ai with Soliplex.

This adapter calls the upstream database backend directly rather than
using create_database_toolset(). This avoids unnecessary FunctionToolset
overhead and gives full control over AG-UI event emission.
"""

from __future__ import annotations

import datetime
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


def _create_task_status_patch(
    task_id: str,
    status: str,
    result: str | None = None,
) -> list[dict[str, Any]]:
    """Create JSON Patch operations for task status update.

    Follows Soliplex convention from soliplex.tools module.

    Args:
        task_id: Task identifier
        status: New status (in_progress, completed, etc.)
        result: Optional result message

    Returns:
        List of JSON Patch operations
    """
    now = datetime.datetime.now(datetime.UTC).isoformat()
    patches: list[dict[str, Any]] = [
        {
            "op": "replace",
            "path": f"/task_list/tasks/{task_id}/status",
            "value": status,
        },
        {
            "op": "replace",
            "path": f"/task_list/tasks/{task_id}/updated_at",
            "value": now,
        },
    ]
    if result is not None:
        patches.append(
            {
                "op": "replace",
                "path": f"/task_list/tasks/{task_id}/result",
                "value": result,
            }
        )
    return patches


class SoliplexSQLAdapter:
    """Adapter wrapping sql-toolset-pydantic-ai for Soliplex.

    Provides:
    - AG-UI state delta events for task progress
    - Integration with Soliplex AgentDependencies
    - Soliplex ToolConfig compatibility

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

    def _emit_task_progress(
        self,
        agui_emitter: Any,
        task_id: str | None,
        status: str,
        result: str | None = None,
    ) -> None:
        """Emit AG-UI state delta for task progress.

        Args:
            agui_emitter: Soliplex AG-UI emitter
            task_id: Task ID to update (None = no emission)
            status: New status value
            result: Optional result message
        """
        if task_id is None or agui_emitter is None:
            return

        try:
            # Import here to avoid hard dependency on soliplex
            from soliplex.agui.events import StateDeltaEvent

            event = StateDeltaEvent(
                delta=_create_task_status_patch(task_id, status, result)
            )
            agui_emitter.emit(event)
        except ImportError:
            # Soliplex not installed, skip event emission
            pass

    async def list_tables(
        self,
        agui_emitter: Any = None,
        related_task_id: str | None = None,
    ) -> list[str]:
        """List all tables in the database.

        Args:
            agui_emitter: Optional AG-UI emitter for progress
            related_task_id: Optional task ID for progress updates

        Returns:
            List of table names
        """
        self._emit_task_progress(agui_emitter, related_task_id, "in_progress")

        try:
            tables = await self._sql_deps.database.get_tables()
        except Exception as e:
            self._emit_task_progress(
                agui_emitter,
                related_task_id,
                "in_progress",
                f"Error: {e}",
            )
            raise
        else:
            self._emit_task_progress(
                agui_emitter,
                related_task_id,
                "completed",
                f"Found {len(tables)} tables",
            )
            return tables

    async def get_schema(
        self,
        agui_emitter: Any = None,
        related_task_id: str | None = None,
    ) -> dict[str, Any]:
        """Get database schema overview.

        Args:
            agui_emitter: Optional AG-UI emitter for progress
            related_task_id: Optional task ID for progress updates

        Returns:
            Schema information with tables, columns, row counts
        """
        self._emit_task_progress(agui_emitter, related_task_id, "in_progress")

        try:
            schema = await self._sql_deps.database.get_schema()

            self._emit_task_progress(
                agui_emitter,
                related_task_id,
                "completed",
                f"Retrieved schema with {len(schema.tables)} tables",
            )

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

        except Exception as e:
            self._emit_task_progress(
                agui_emitter,
                related_task_id,
                "in_progress",
                f"Error: {e}",
            )
            raise

    async def describe_table(
        self,
        table_name: str,
        agui_emitter: Any = None,
        related_task_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Get detailed information about a specific table.

        Args:
            table_name: Name of the table to describe
            agui_emitter: Optional AG-UI emitter for progress
            related_task_id: Optional task ID for progress updates

        Returns:
            Table information or None if table not found
        """
        self._emit_task_progress(agui_emitter, related_task_id, "in_progress")

        try:
            table_info = await self._sql_deps.database.get_table_info(
                table_name
            )

            if table_info is None:
                self._emit_task_progress(
                    agui_emitter,
                    related_task_id,
                    "completed",
                    f"Table '{table_name}' not found",
                )
                return None

            self._emit_task_progress(
                agui_emitter,
                related_task_id,
                "completed",
                f"Described table '{table_name}'",
            )

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

        except Exception as e:
            self._emit_task_progress(
                agui_emitter,
                related_task_id,
                "in_progress",
                f"Error: {e}",
            )
            raise

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
        agui_emitter: Any = None,
        related_task_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute a SQL query and return results.

        Args:
            sql_query: SQL query to execute
            max_rows: Maximum rows to return
            agui_emitter: Optional AG-UI emitter for progress
            related_task_id: Optional task ID for progress updates

        Returns:
            Query results with columns, rows, metadata

        Raises:
            QueryExecutionError: If mutation attempted in read-only mode
        """
        # Enforce read-only mode
        self._check_read_only(sql_query)

        self._emit_task_progress(agui_emitter, related_task_id, "in_progress")

        try:
            result = await self._sql_deps.database.execute(sql_query)

            limit = max_rows or self._sql_deps.max_rows
            rows = result.rows[:limit]
            truncated = len(result.rows) > limit

            self._emit_task_progress(
                agui_emitter,
                related_task_id,
                "completed",
                f"Returned {len(rows)} rows",
            )

            return {
                "columns": result.columns,
                "rows": [list(row) for row in rows],
                "row_count": len(rows),
                "truncated": truncated,
                "execution_time_ms": result.execution_time_ms,
            }

        except Exception as e:
            self._emit_task_progress(
                agui_emitter,
                related_task_id,
                "in_progress",
                f"Error: {e}",
            )
            raise

    async def explain_query(
        self,
        sql_query: str,
        agui_emitter: Any = None,
        related_task_id: str | None = None,
    ) -> str:
        """Get the execution plan for a SQL query.

        Args:
            sql_query: SQL query to analyze
            agui_emitter: Optional AG-UI emitter for progress
            related_task_id: Optional task ID for progress updates

        Returns:
            Query execution plan as string
        """
        self._emit_task_progress(agui_emitter, related_task_id, "in_progress")

        try:
            plan = await self._sql_deps.database.explain(sql_query)
        except Exception as e:
            self._emit_task_progress(
                agui_emitter,
                related_task_id,
                "in_progress",
                f"Error: {e}",
            )
            raise
        else:
            self._emit_task_progress(
                agui_emitter,
                related_task_id,
                "completed",
                "Query plan generated",
            )
            return plan

    async def sample_query(
        self,
        sql_query: str,
        limit: int = 5,
        agui_emitter: Any = None,
        related_task_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute a sample query for quick data exploration.

        Args:
            sql_query: SQL query to execute
            limit: Maximum rows (default: 5)
            agui_emitter: Optional AG-UI emitter for progress
            related_task_id: Optional task ID for progress updates

        Returns:
            Sample query results
        """
        return await self.query(
            sql_query,
            max_rows=limit,
            agui_emitter=agui_emitter,
            related_task_id=related_task_id,
        )

    async def close(self) -> None:
        """Close the database connection."""
        await self._sql_deps.database.close()
