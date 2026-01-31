"""Tests for exceptions module."""

from __future__ import annotations

import pytest

from soliplex_sql.exceptions import ConfigurationError
from soliplex_sql.exceptions import DatabaseConnectionError
from soliplex_sql.exceptions import QueryExecutionError
from soliplex_sql.exceptions import SoliplexSqlError
from soliplex_sql.exceptions import UnsupportedDatabaseError


class TestExceptions:
    """Tests for custom exceptions."""

    def test_base_exception(self) -> None:
        """SoliplexSqlError should be base for all."""
        exc = SoliplexSqlError("test error")
        assert str(exc) == "test error"
        assert isinstance(exc, Exception)

    def test_configuration_error_inheritance(self) -> None:
        """ConfigurationError should inherit from base."""
        exc = ConfigurationError("bad config")
        assert isinstance(exc, SoliplexSqlError)
        assert isinstance(exc, Exception)

    def test_database_connection_error_inheritance(self) -> None:
        """DatabaseConnectionError should inherit from base."""
        exc = DatabaseConnectionError("connection failed")
        assert isinstance(exc, SoliplexSqlError)

    def test_query_execution_error_inheritance(self) -> None:
        """QueryExecutionError should inherit from base."""
        exc = QueryExecutionError("query failed")
        assert isinstance(exc, SoliplexSqlError)

    def test_unsupported_database_error_inheritance(self) -> None:
        """UnsupportedDatabaseError should inherit from base."""
        exc = UnsupportedDatabaseError("mysql not supported")
        assert isinstance(exc, SoliplexSqlError)

    def test_exceptions_can_be_caught_by_base(self) -> None:
        """All exceptions should be catchable by base class."""
        exceptions = [
            ConfigurationError("test"),
            DatabaseConnectionError("test"),
            QueryExecutionError("test"),
            UnsupportedDatabaseError("test"),
        ]

        for exc in exceptions:
            with pytest.raises(SoliplexSqlError):
                raise exc
