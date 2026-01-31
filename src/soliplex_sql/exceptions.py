"""Custom exceptions for soliplex_sql."""

from __future__ import annotations


class SoliplexSqlError(Exception):
    """Base exception for soliplex_sql errors."""


class ConfigurationError(SoliplexSqlError):
    """Raised when configuration is invalid or missing."""


class DatabaseConnectionError(SoliplexSqlError):
    """Raised when database connection fails."""


class QueryExecutionError(SoliplexSqlError):
    """Raised when query execution fails."""


class UnsupportedDatabaseError(SoliplexSqlError):
    """Raised when database URL scheme is not supported."""
