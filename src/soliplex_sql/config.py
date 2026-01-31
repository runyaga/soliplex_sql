"""Soliplex ToolConfig integration for SQL tools.

Bridges sql-toolset-pydantic-ai with Soliplex's configuration system.
"""

from __future__ import annotations

import dataclasses
import pathlib
from typing import TYPE_CHECKING
from typing import Any

from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from soliplex_sql.exceptions import UnsupportedDatabaseError

if TYPE_CHECKING:
    from sql_toolset_pydantic_ai import SQLDatabaseDeps
    from sql_toolset_pydantic_ai.sql.protocol import SQLDatabaseProtocol


class SQLToolSettings(BaseSettings):
    """Environment-based configuration for SQL tools.

    Environment variables:
        SOLIPLEX_SQL_DATABASE_URL: Connection string
        SOLIPLEX_SQL_READ_ONLY: Enforce read-only mode (default: True)
        SOLIPLEX_SQL_MAX_ROWS: Max rows returned (default: 100)
        SOLIPLEX_SQL_QUERY_TIMEOUT: Query timeout seconds (default: 30.0)
    """

    model_config = SettingsConfigDict(env_prefix="SOLIPLEX_SQL_")

    database_url: str = "sqlite:///./data.db"
    read_only: bool = True
    max_rows: int = 100
    query_timeout: float = 30.0


def _create_backend(database_url: str) -> SQLDatabaseProtocol:
    """Create appropriate backend from database URL.

    Args:
        database_url: Database connection string

    Returns:
        SQLDatabaseProtocol implementation

    Raises:
        UnsupportedDatabaseError: If URL scheme is not supported
    """
    from sql_toolset_pydantic_ai import PostgreSQLDatabase
    from sql_toolset_pydantic_ai import SQLiteDatabase

    if database_url.startswith("sqlite"):
        path = database_url.replace("sqlite:///", "")
        return SQLiteDatabase(path)
    elif database_url.startswith("postgresql"):
        return PostgreSQLDatabase(database_url)
    else:
        msg = f"Unsupported database URL: {database_url}. "
        msg += "Supported: sqlite:///, postgresql://"
        raise UnsupportedDatabaseError(msg)


# Load environment variables at module level (fallback defaults)
_env_settings = SQLToolSettings()


@dataclasses.dataclass
class SQLToolConfigBase:
    """Base configuration for SQL tools.

    Soliplex requires 1:1 mapping between tool_name and config class.
    Each tool gets a subclass with its specific tool_name.

    Defaults come from environment variables via SQLToolSettings.
    Room configs can override any setting.
    """

    database_url: str = dataclasses.field(
        default_factory=lambda: _env_settings.database_url
    )
    read_only: bool = dataclasses.field(
        default_factory=lambda: _env_settings.read_only
    )
    max_rows: int = dataclasses.field(
        default_factory=lambda: _env_settings.max_rows
    )
    query_timeout: float = dataclasses.field(
        default_factory=lambda: _env_settings.query_timeout
    )

    agui_feature_names: tuple[str, ...] = ()

    _installation_config: Any = dataclasses.field(default=None, repr=False)
    _config_path: pathlib.Path | None = dataclasses.field(
        default=None, repr=False
    )

    @classmethod
    def from_yaml(
        cls,
        installation_config: Any,
        config_path: pathlib.Path,
        config: dict[str, Any],
    ) -> SQLToolConfigBase:
        """Create from Soliplex YAML configuration."""
        return cls(
            database_url=config.get(
                "database_url", _env_settings.database_url
            ),
            read_only=config.get("read_only", _env_settings.read_only),
            max_rows=config.get("max_rows", _env_settings.max_rows),
            query_timeout=config.get(
                "query_timeout", _env_settings.query_timeout
            ),
            _installation_config=installation_config,
            _config_path=config_path,
        )

    @property
    def kind(self) -> str:
        """Tool kind identifier (shared across all SQL tools)."""
        return "sql"

    def create_deps(self) -> SQLDatabaseDeps:
        """Create SQLDatabaseDeps from this configuration."""
        from sql_toolset_pydantic_ai import SQLDatabaseDeps

        backend = _create_backend(self.database_url)
        return SQLDatabaseDeps(
            database=backend,
            read_only=self.read_only,
            max_rows=self.max_rows,
            query_timeout=self.query_timeout,
        )


@dataclasses.dataclass
class ListTablesConfig(SQLToolConfigBase):
    """Config for list_tables tool."""

    tool_name: str = "soliplex_sql.tools.list_tables"


@dataclasses.dataclass
class GetSchemaConfig(SQLToolConfigBase):
    """Config for get_schema tool."""

    tool_name: str = "soliplex_sql.tools.get_schema"


@dataclasses.dataclass
class DescribeTableConfig(SQLToolConfigBase):
    """Config for describe_table tool."""

    tool_name: str = "soliplex_sql.tools.describe_table"


@dataclasses.dataclass
class QueryConfig(SQLToolConfigBase):
    """Config for query tool."""

    tool_name: str = "soliplex_sql.tools.query"


@dataclasses.dataclass
class ExplainQueryConfig(SQLToolConfigBase):
    """Config for explain_query tool."""

    tool_name: str = "soliplex_sql.tools.explain_query"


@dataclasses.dataclass
class SampleQueryConfig(SQLToolConfigBase):
    """Config for sample_query tool."""

    tool_name: str = "soliplex_sql.tools.sample_query"
