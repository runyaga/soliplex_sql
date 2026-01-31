"""Tests for configuration module."""

from __future__ import annotations

import pytest

from soliplex_sql.config import DescribeTableConfig
from soliplex_sql.config import ExplainQueryConfig
from soliplex_sql.config import GetSchemaConfig
from soliplex_sql.config import ListTablesConfig
from soliplex_sql.config import QueryConfig
from soliplex_sql.config import SampleQueryConfig
from soliplex_sql.config import SQLToolConfigBase
from soliplex_sql.config import SQLToolSettings
from soliplex_sql.config import _create_backend
from soliplex_sql.exceptions import UnsupportedDatabaseError


class TestSQLToolSettings:
    """Tests for environment-based settings."""

    def test_default_values(self) -> None:
        """Default settings should be valid."""
        settings = SQLToolSettings()

        assert settings.read_only is True
        assert settings.max_rows == 100
        assert settings.query_timeout == 30.0
        assert "sqlite" in settings.database_url

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Environment variables override defaults."""
        monkeypatch.setenv("SOLIPLEX_SQL_READ_ONLY", "false")
        monkeypatch.setenv("SOLIPLEX_SQL_MAX_ROWS", "500")
        monkeypatch.setenv("SOLIPLEX_SQL_QUERY_TIMEOUT", "60.0")

        settings = SQLToolSettings()

        assert settings.read_only is False
        assert settings.max_rows == 500
        assert settings.query_timeout == 60.0


class TestCreateBackend:
    """Tests for backend factory."""

    def test_sqlite_backend(self, temp_db_path: str) -> None:
        """Should create SQLite backend."""
        backend = _create_backend(f"sqlite:///{temp_db_path}")
        assert backend is not None

    def test_unsupported_raises(self) -> None:
        """Should raise for unsupported URLs."""
        with pytest.raises(UnsupportedDatabaseError, match="Unsupported"):
            _create_backend("mysql://localhost/db")

    def test_unsupported_shows_supported_schemes(self) -> None:
        """Error message should show supported schemes."""
        with pytest.raises(UnsupportedDatabaseError) as exc_info:
            _create_backend("oracle://localhost/db")

        assert "sqlite" in str(exc_info.value)
        assert "postgresql" in str(exc_info.value)


class TestSQLToolConfigBase:
    """Tests for base configuration class."""

    def test_default_values_from_env(self) -> None:
        """Defaults should come from environment settings."""
        config = SQLToolConfigBase()

        # Should match SQLToolSettings defaults
        assert config.read_only is True
        assert config.max_rows == 100
        assert config.query_timeout == 30.0

    def test_kind_property(self) -> None:
        """Kind should be 'sql'."""
        config = SQLToolConfigBase()
        assert config.kind == "sql"

    def test_from_yaml(self) -> None:
        """Should create from YAML config dict."""
        config = SQLToolConfigBase.from_yaml(
            installation_config=None,
            config_path=None,
            config={
                "database_url": "sqlite:///./test.db",
                "read_only": False,
                "max_rows": 200,
            },
        )

        assert config.database_url == "sqlite:///./test.db"
        assert config.read_only is False
        assert config.max_rows == 200

    def test_from_yaml_uses_env_defaults(self) -> None:
        """YAML with missing fields should use env defaults."""
        config = SQLToolConfigBase.from_yaml(
            installation_config=None,
            config_path=None,
            config={},
        )

        # Should use defaults from SQLToolSettings
        assert config.read_only is True
        assert config.max_rows == 100


class TestPerToolConfigs:
    """Tests for per-tool configuration classes."""

    def test_list_tables_config_tool_name(self) -> None:
        """ListTablesConfig should have correct tool_name and unique kind."""
        config = ListTablesConfig()
        assert config.tool_name == "soliplex_sql.tools.list_tables"
        assert config.kind == "sql_list_tables"

    def test_query_config_tool_name(self) -> None:
        """QueryConfig should have correct tool_name and unique kind."""
        config = QueryConfig()
        assert config.tool_name == "soliplex_sql.tools.query"
        assert config.kind == "sql_query"

    def test_describe_table_config_tool_name(self) -> None:
        """DescribeTableConfig has correct tool_name and unique kind."""
        config = DescribeTableConfig()
        assert config.tool_name == "soliplex_sql.tools.describe_table"
        assert config.kind == "sql_describe_table"

    def test_get_schema_config(self) -> None:
        """GetSchemaConfig should have correct tool_name and kind."""
        config = GetSchemaConfig()
        assert config.tool_name == "soliplex_sql.tools.get_schema"
        assert config.kind == "sql_get_schema"

    def test_explain_query_config(self) -> None:
        """ExplainQueryConfig should have correct tool_name and kind."""
        config = ExplainQueryConfig()
        assert config.tool_name == "soliplex_sql.tools.explain_query"
        assert config.kind == "sql_explain_query"

    def test_sample_query_config(self) -> None:
        """SampleQueryConfig should have correct tool_name and kind."""
        config = SampleQueryConfig()
        assert config.tool_name == "soliplex_sql.tools.sample_query"
        assert config.kind == "sql_sample_query"

    def test_configs_have_unique_kinds(self) -> None:
        """All SQL configs should have unique kinds starting with 'sql'."""
        configs = [
            ListTablesConfig(),
            GetSchemaConfig(),
            DescribeTableConfig(),
            QueryConfig(),
            ExplainQueryConfig(),
            SampleQueryConfig(),
        ]

        kinds = {c.kind for c in configs}
        # Each config has unique kind
        assert len(kinds) == 6
        # All start with "sql"
        assert all(k.startswith("sql") for k in kinds)

    def test_tool_property_loads_function(self) -> None:
        """Tool property should import and return the tool function."""
        config = ListTablesConfig()
        tool_func = config.tool

        # Should return the actual function
        from soliplex_sql.tools import list_tables

        assert tool_func is list_tables

    def test_tool_requires_property(self) -> None:
        """Tool requires should return 'fastapi_context'."""
        config = QueryConfig()
        assert config.tool_requires == "fastapi_context"

    def test_base_config_tool_raises_without_tool_name(self) -> None:
        """Base config tool property should raise without tool_name."""
        config = SQLToolConfigBase()
        with pytest.raises(AttributeError, match="tool_name"):
            _ = config.tool

    def test_configs_inherit_settings(self) -> None:
        """Per-tool configs should inherit base settings."""
        config = QueryConfig(
            database_url="postgresql://localhost/test",
            max_rows=500,
        )

        assert config.database_url == "postgresql://localhost/test"
        assert config.max_rows == 500
        assert config.tool_name == "soliplex_sql.tools.query"
