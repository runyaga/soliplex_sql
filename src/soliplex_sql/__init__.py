"""Soliplex SQL Adapter.

Integrates sql-toolset-pydantic-ai into the Soliplex framework.
"""

from __future__ import annotations

# Configuration
from soliplex_sql.config import SQLToolConfig
from soliplex_sql.config import SQLToolSettings

# Exceptions
from soliplex_sql.exceptions import ConfigurationError
from soliplex_sql.exceptions import DatabaseConnectionError
from soliplex_sql.exceptions import QueryExecutionError
from soliplex_sql.exceptions import SoliplexSqlError
from soliplex_sql.exceptions import UnsupportedDatabaseError

# Tools (for direct import in room configs)
from soliplex_sql.tools import close_all
from soliplex_sql.tools import describe_table
from soliplex_sql.tools import explain_query
from soliplex_sql.tools import get_schema
from soliplex_sql.tools import list_tables
from soliplex_sql.tools import query
from soliplex_sql.tools import sample_query

__all__ = [
    "ConfigurationError",
    "DatabaseConnectionError",
    "QueryExecutionError",
    "SQLToolConfig",
    "SQLToolSettings",
    "SoliplexSqlError",
    "UnsupportedDatabaseError",
    "close_all",
    "describe_table",
    "explain_query",
    "get_schema",
    "list_tables",
    "query",
    "sample_query",
]

__version__ = "0.1.0dev0"
