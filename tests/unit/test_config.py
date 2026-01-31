"""Tests for configuration module."""

from __future__ import annotations

import pytest

from soliplex_sql.config import SQLToolConfig
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


class TestSQLToolConfig:
    """Tests for the unified SQLToolConfig class."""

    def test_default_values_from_env(self) -> None:
        """Defaults should come from environment settings."""
        config = SQLToolConfig(tool_name="soliplex_sql.tools.query")

        # Should match SQLToolSettings defaults
        assert config.read_only is True
        assert config.max_rows == 100
        assert config.query_timeout == 30.0

    def test_kind_property_returns_sql(self) -> None:
        """Kind property should always return 'sql'."""
        config = SQLToolConfig(tool_name="soliplex_sql.tools.list_tables")
        assert config.kind == "sql"

    def test_kind_is_sql_regardless_of_tool_name(self) -> None:
        """Kind should be 'sql' for all SQL tools."""
        tools = [
            "soliplex_sql.tools.list_tables",
            "soliplex_sql.tools.get_schema",
            "soliplex_sql.tools.describe_table",
            "soliplex_sql.tools.query",
            "soliplex_sql.tools.explain_query",
            "soliplex_sql.tools.sample_query",
        ]
        for tool_name in tools:
            config = SQLToolConfig(tool_name=tool_name)
            assert config.kind == "sql"

    def test_from_yaml(self) -> None:
        """Should create from YAML config dict."""
        config = SQLToolConfig.from_yaml(
            installation_config=None,
            config_path=None,
            config={
                "tool_name": "soliplex_sql.tools.query",
                "database_url": "sqlite:///./test.db",
                "read_only": False,
                "max_rows": 200,
            },
        )

        assert config.tool_name == "soliplex_sql.tools.query"
        assert config.database_url == "sqlite:///./test.db"
        assert config.read_only is False
        assert config.max_rows == 200

    def test_from_yaml_uses_env_defaults(self) -> None:
        """YAML with missing fields should use env defaults."""
        config = SQLToolConfig.from_yaml(
            installation_config=None,
            config_path=None,
            config={"tool_name": "soliplex_sql.tools.query"},
        )

        # Should use defaults from SQLToolSettings
        assert config.read_only is True
        assert config.max_rows == 100

    def test_tool_property_loads_function(self) -> None:
        """Tool property should import and return the tool function."""
        config = SQLToolConfig(tool_name="soliplex_sql.tools.list_tables")
        tool_func = config.tool

        # Should return the actual function
        from soliplex_sql.tools import list_tables

        assert tool_func is list_tables

    def test_tool_requires_property(self) -> None:
        """Tool requires should return 'tool_config' for injection."""
        from soliplex.config import ToolRequires

        config = SQLToolConfig(tool_name="soliplex_sql.tools.query")
        assert config.tool_requires == ToolRequires.TOOL_CONFIG

    def test_config_requires_tool_name(self) -> None:
        """SQLToolConfig requires tool_name (inherited from ToolConfig)."""
        with pytest.raises(TypeError, match="tool_name"):
            SQLToolConfig()

    def test_config_accepts_custom_settings(self) -> None:
        """SQLToolConfig should accept custom settings."""
        config = SQLToolConfig(
            tool_name="soliplex_sql.tools.query",
            database_url="postgresql://localhost/test",
            max_rows=500,
        )

        assert config.database_url == "postgresql://localhost/test"
        assert config.max_rows == 500
        assert config.tool_name == "soliplex_sql.tools.query"

    def test_create_deps(self, temp_db_path: str) -> None:
        """Should create SQLDatabaseDeps from configuration."""
        config = SQLToolConfig(
            tool_name="soliplex_sql.tools.query",
            database_url=f"sqlite:///{temp_db_path}",
            read_only=True,
            max_rows=50,
            query_timeout=15.0,
        )

        deps = config.create_deps()

        assert deps.read_only is True
        assert deps.max_rows == 50
        assert deps.query_timeout == 15.0
