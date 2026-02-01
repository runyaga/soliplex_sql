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
from soliplex.config import ToolConfig

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


def _parse_postgres_url(url: str) -> dict[str, str]:
    """Parse PostgreSQL URL into components.

    Supports formats:
        postgresql://user:password@host:port/database
        postgresql+asyncpg://user:password@host:port/database

    Args:
        url: PostgreSQL connection URL

    Returns:
        Dict with user, password, host, db keys
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return {
        "user": parsed.username or "postgres",
        "password": parsed.password or "",
        "host": f"{parsed.hostname or 'localhost'}:{parsed.port or 5432}",
        "db": parsed.path.lstrip("/") or "postgres",
    }


def _create_backend(
    database_url: str,
    read_only: bool = True,
) -> SQLDatabaseProtocol:
    """Create appropriate backend from database URL.

    Args:
        database_url: Database connection string
        read_only: Whether database should be read-only

    Returns:
        SQLDatabaseProtocol implementation

    Raises:
        UnsupportedDatabaseError: If URL scheme is not supported
    """
    from sql_toolset_pydantic_ai import PostgreSQLDatabase
    from sql_toolset_pydantic_ai import SQLiteDatabase

    if database_url.startswith("sqlite"):
        path = database_url.replace("sqlite:///", "")
        return SQLiteDatabase(path, read_only=read_only)
    elif database_url.startswith("postgresql"):
        params = _parse_postgres_url(database_url)
        return PostgreSQLDatabase(
            user=params["user"],
            password=params["password"],
            host=params["host"],
            db=params["db"],
            read_only=read_only,
        )
    else:
        msg = f"Unsupported database URL: {database_url}. "
        msg += "Supported: sqlite:///, postgresql://"
        raise UnsupportedDatabaseError(msg)


def _get_env_settings() -> SQLToolSettings:
    """Lazy-load environment settings.

    Returns:
        SQLToolSettings instance with values from environment.
    """
    return SQLToolSettings()


@dataclasses.dataclass
class SQLToolConfig(ToolConfig):
    """Configuration for SQL tools.

    Inherits from soliplex.config.ToolConfig for full Soliplex integration.
    Single config class for all SQL tools - tool_name comes from room config.

    Defaults come from environment variables via SQLToolSettings (lazy loaded).
    Room configs can override any setting.
    """

    # SQL-specific fields with lazy env var defaults
    database_url: str = dataclasses.field(
        default_factory=lambda: _get_env_settings().database_url
    )
    read_only: bool = dataclasses.field(
        default_factory=lambda: _get_env_settings().read_only
    )
    max_rows: int = dataclasses.field(
        default_factory=lambda: _get_env_settings().max_rows
    )
    query_timeout: float = dataclasses.field(
        default_factory=lambda: _get_env_settings().query_timeout
    )

    # NOTE: Inherit 'kind' from ToolConfig base class to avoid registry
    # collisions when multiple SQL tools are used in the same room.
    # ToolConfig.kind derives unique identifier from tool_name.

    @classmethod
    def from_yaml(
        cls,
        installation_config: Any,
        config_path: pathlib.Path,
        config: dict[str, Any],
    ) -> SQLToolConfig:
        """Create from Soliplex YAML configuration.

        Uses lazy loading for env settings to support testing.
        """
        env_settings = _get_env_settings()
        return cls(
            tool_name=config.get("tool_name", ""),
            database_url=config.get("database_url", env_settings.database_url),
            read_only=config.get("read_only", env_settings.read_only),
            max_rows=config.get("max_rows", env_settings.max_rows),
            query_timeout=config.get(
                "query_timeout", env_settings.query_timeout
            ),
            _installation_config=installation_config,
            _config_path=config_path,
        )

    def create_deps(self) -> SQLDatabaseDeps:
        """Create SQLDatabaseDeps from this configuration."""
        from sql_toolset_pydantic_ai import SQLDatabaseDeps

        backend = _create_backend(self.database_url, read_only=self.read_only)
        return SQLDatabaseDeps(
            database=backend,
            read_only=self.read_only,
            max_rows=self.max_rows,
            query_timeout=self.query_timeout,
        )


# Per-tool config classes for Soliplex registration.
# Soliplex requires class-level tool_name for TOOL_CONFIG_CLASSES_BY_TOOL_NAME
# registry. These subclasses inherit all logic from SQLToolConfig.


@dataclasses.dataclass
class ListTablesConfig(SQLToolConfig):
    """Config for list_tables tool."""

    tool_name: str = "soliplex_sql.tools.list_tables"


@dataclasses.dataclass
class GetSchemaConfig(SQLToolConfig):
    """Config for get_schema tool."""

    tool_name: str = "soliplex_sql.tools.get_schema"


@dataclasses.dataclass
class DescribeTableConfig(SQLToolConfig):
    """Config for describe_table tool."""

    tool_name: str = "soliplex_sql.tools.describe_table"


@dataclasses.dataclass
class QueryConfig(SQLToolConfig):
    """Config for query tool."""

    tool_name: str = "soliplex_sql.tools.query"


@dataclasses.dataclass
class ExplainQueryConfig(SQLToolConfig):
    """Config for explain_query tool."""

    tool_name: str = "soliplex_sql.tools.explain_query"


@dataclasses.dataclass
class SampleQueryConfig(SQLToolConfig):
    """Config for sample_query tool."""

    tool_name: str = "soliplex_sql.tools.sample_query"
