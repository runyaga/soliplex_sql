"""Soliplex-compatible tool functions.

These tools use Soliplex's native tool_config injection:
- tool_config: SQLToolConfig automatically injected by Soliplex
- Async tool functions
- Type-safe return values
"""

from __future__ import annotations

import asyncio
from typing import Any

from soliplex_sql.adapter import SoliplexSQLAdapter
from soliplex_sql.config import SQLToolConfig

# Module-level cache: config_tuple -> adapter (supports concurrent rooms)
# Using tuple as key (not hash) for stability across processes
_adapter_cache: dict[tuple, SoliplexSQLAdapter] = {}
_adapter_lock = asyncio.Lock()


async def _get_adapter(config: SQLToolConfig) -> SoliplexSQLAdapter:
    """Get or create SQL adapter from config.

    Uses dict-based caching to support multiple concurrent database
    connections (e.g., Room A -> Sales DB, Room B -> HR DB).
    Critical for PostgreSQL connection pooling performance.

    Args:
        config: SQLToolConfig with database settings

    Returns:
        SoliplexSQLAdapter instance (cached)
    """
    # Cache key based on connection parameters (tuple, not hash)
    cache_key = (
        config.database_url,
        config.read_only,
        config.max_rows,
    )

    # Fast path: check cache without lock
    if cache_key in _adapter_cache:
        return _adapter_cache[cache_key]

    # Slow path: acquire async lock and create adapter
    async with _adapter_lock:
        # Double-check after acquiring lock
        if cache_key in _adapter_cache:
            return _adapter_cache[cache_key]

        # Create new adapter and cache it
        sql_deps = config.create_deps()
        adapter = SoliplexSQLAdapter(sql_deps)
        _adapter_cache[cache_key] = adapter

        return adapter


async def list_tables(
    tool_config: SQLToolConfig,
) -> list[str]:
    """List all tables in the database.

    Args:
        tool_config: SQLToolConfig (injected by Soliplex)

    Returns:
        List of table names
    """
    adapter = await _get_adapter(tool_config)
    return await adapter.list_tables()


async def get_schema(
    tool_config: SQLToolConfig,
) -> dict[str, Any]:
    """Get database schema overview.

    Args:
        tool_config: SQLToolConfig (injected by Soliplex)

    Returns:
        Schema information with tables, columns, and row counts
    """
    adapter = await _get_adapter(tool_config)
    return await adapter.get_schema()


async def describe_table(
    tool_config: SQLToolConfig,
    table_name: str,
) -> dict[str, Any] | None:
    """Get detailed information about a specific table.

    Args:
        tool_config: SQLToolConfig (injected by Soliplex)
        table_name: Name of the table to describe

    Returns:
        Table information including columns, types, constraints
    """
    adapter = await _get_adapter(tool_config)
    return await adapter.describe_table(table_name)


async def query(
    tool_config: SQLToolConfig,
    sql_query: str,
    max_rows: int | None = None,
) -> dict[str, Any]:
    """Execute a SQL query and return results.

    Args:
        tool_config: SQLToolConfig (injected by Soliplex)
        sql_query: SQL query to execute
        max_rows: Maximum rows to return (optional)

    Returns:
        Query results with columns, rows, and metadata
    """
    adapter = await _get_adapter(tool_config)
    return await adapter.query(sql_query, max_rows)


async def explain_query(
    tool_config: SQLToolConfig,
    sql_query: str,
) -> str:
    """Get the execution plan for a SQL query.

    Args:
        tool_config: SQLToolConfig (injected by Soliplex)
        sql_query: SQL query to analyze

    Returns:
        Query execution plan
    """
    adapter = await _get_adapter(tool_config)
    return await adapter.explain_query(sql_query)


async def sample_query(
    tool_config: SQLToolConfig,
    sql_query: str,
    limit: int = 5,
) -> dict[str, Any]:
    """Execute a sample query for quick data exploration.

    Args:
        tool_config: SQLToolConfig (injected by Soliplex)
        sql_query: SQL query to execute
        limit: Maximum rows (default: 5)

    Returns:
        Sample query results
    """
    adapter = await _get_adapter(tool_config)
    return await adapter.sample_query(sql_query, limit)


async def close_all() -> None:
    """Close all cached database connections.

    Call this on application shutdown for graceful cleanup.
    Async-safe: acquires async lock before accessing cache.
    """
    async with _adapter_lock:
        adapters = list(_adapter_cache.values())
        _adapter_cache.clear()

    # Close outside lock to avoid holding lock during I/O
    for adapter in adapters:
        await adapter.close()
