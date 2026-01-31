"""Soliplex-compatible tool functions.

These tools follow Soliplex conventions:
- Accept RunContext[AgentDependencies]
- Support related_task_id for task progress
- Emit AG-UI events via agui_emitter

These tools follow pydantic-ai idioms:
- RunContext dependency injection
- Async tool functions
- Type-safe return values
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from soliplex_sql.adapter import SoliplexSQLAdapter
from soliplex_sql.config import SQLToolConfigBase
from soliplex_sql.config import SQLToolSettings

if TYPE_CHECKING:
    import pydantic_ai

# Module-level cache: config_hash -> adapter (supports concurrent rooms)
_adapter_cache: dict[int, SoliplexSQLAdapter] = {}


def _get_config_from_context(ctx: Any) -> SQLToolConfigBase | None:
    """Extract SQL config from context if available.

    Args:
        ctx: RunContext with deps

    Returns:
        SQLToolConfigBase or None
    """
    if not hasattr(ctx, "deps"):
        return None

    deps = ctx.deps
    if not hasattr(deps, "tool_configs"):
        return None

    tool_configs = deps.tool_configs

    # Look for any SQL tool config (they share 'kind')
    for config in tool_configs.values():
        if hasattr(config, "kind") and config.kind == "sql":
            return config

    return None


def _get_adapter(ctx: Any) -> SoliplexSQLAdapter:
    """Get or create SQL adapter from context.

    Uses dict-based caching to support multiple concurrent database
    connections (e.g., Room A -> Sales DB, Room B -> HR DB).
    Critical for PostgreSQL connection pooling performance.

    Args:
        ctx: RunContext with deps

    Returns:
        SoliplexSQLAdapter instance (cached)
    """
    tool_config = _get_config_from_context(ctx)

    if tool_config is None:
        # Fall back to environment-based configuration
        settings = SQLToolSettings()
        tool_config = SQLToolConfigBase(
            database_url=settings.database_url,
            read_only=settings.read_only,
            max_rows=settings.max_rows,
            query_timeout=settings.query_timeout,
        )

    # Cache key based on connection parameters
    config_hash = hash(
        (
            tool_config.database_url,
            tool_config.read_only,
            tool_config.max_rows,
        )
    )

    # Check cache dict (supports multiple DBs concurrently)
    if config_hash in _adapter_cache:
        return _adapter_cache[config_hash]

    # Create new adapter and cache it
    sql_deps = tool_config.create_deps()
    adapter = SoliplexSQLAdapter(sql_deps)
    _adapter_cache[config_hash] = adapter

    return adapter


def _get_agui_emitter(ctx: Any) -> Any:
    """Extract AG-UI emitter from context if available.

    Args:
        ctx: RunContext with deps

    Returns:
        agui_emitter or None
    """
    if not hasattr(ctx, "deps"):
        return None
    if not hasattr(ctx.deps, "agui_emitter"):
        return None
    return ctx.deps.agui_emitter


async def list_tables(
    ctx: pydantic_ai.RunContext[Any],
    related_task_id: str | None = None,
) -> list[str]:
    """List all tables in the database.

    Args:
        ctx: PydanticAI RunContext
        related_task_id: Optional task ID to update with progress

    Returns:
        List of table names
    """
    adapter = _get_adapter(ctx)
    emitter = _get_agui_emitter(ctx)
    return await adapter.list_tables(emitter, related_task_id)


async def get_schema(
    ctx: pydantic_ai.RunContext[Any],
    related_task_id: str | None = None,
) -> dict[str, Any]:
    """Get database schema overview.

    Args:
        ctx: PydanticAI RunContext
        related_task_id: Optional task ID to update with progress

    Returns:
        Schema information with tables, columns, and row counts
    """
    adapter = _get_adapter(ctx)
    emitter = _get_agui_emitter(ctx)
    return await adapter.get_schema(emitter, related_task_id)


async def describe_table(
    ctx: pydantic_ai.RunContext[Any],
    table_name: str,
    related_task_id: str | None = None,
) -> dict[str, Any] | None:
    """Get detailed information about a specific table.

    Args:
        ctx: PydanticAI RunContext
        table_name: Name of the table to describe
        related_task_id: Optional task ID to update with progress

    Returns:
        Table information including columns, types, constraints
    """
    adapter = _get_adapter(ctx)
    emitter = _get_agui_emitter(ctx)
    return await adapter.describe_table(table_name, emitter, related_task_id)


async def query(
    ctx: pydantic_ai.RunContext[Any],
    sql_query: str,
    max_rows: int | None = None,
    related_task_id: str | None = None,
) -> dict[str, Any]:
    """Execute a SQL query and return results.

    Args:
        ctx: PydanticAI RunContext
        sql_query: SQL query to execute
        max_rows: Maximum rows to return (optional)
        related_task_id: Optional task ID to update with progress

    Returns:
        Query results with columns, rows, and metadata
    """
    adapter = _get_adapter(ctx)
    emitter = _get_agui_emitter(ctx)
    return await adapter.query(sql_query, max_rows, emitter, related_task_id)


async def explain_query(
    ctx: pydantic_ai.RunContext[Any],
    sql_query: str,
    related_task_id: str | None = None,
) -> str:
    """Get the execution plan for a SQL query.

    Args:
        ctx: PydanticAI RunContext
        sql_query: SQL query to analyze
        related_task_id: Optional task ID to update with progress

    Returns:
        Query execution plan
    """
    adapter = _get_adapter(ctx)
    emitter = _get_agui_emitter(ctx)
    return await adapter.explain_query(sql_query, emitter, related_task_id)


async def sample_query(
    ctx: pydantic_ai.RunContext[Any],
    sql_query: str,
    limit: int = 5,
    related_task_id: str | None = None,
) -> dict[str, Any]:
    """Execute a sample query for quick data exploration.

    Args:
        ctx: PydanticAI RunContext
        sql_query: SQL query to execute
        limit: Maximum rows (default: 5)
        related_task_id: Optional task ID to update with progress

    Returns:
        Sample query results
    """
    adapter = _get_adapter(ctx)
    emitter = _get_agui_emitter(ctx)
    return await adapter.sample_query(
        sql_query, limit, emitter, related_task_id
    )


async def close_all() -> None:
    """Close all cached database connections.

    Call this on application shutdown for graceful cleanup.
    """
    for adapter in _adapter_cache.values():
        await adapter.close()
    _adapter_cache.clear()
