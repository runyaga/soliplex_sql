# Soliplex SQL Adapter - Implementation Plan

## Executive Summary

This document outlines the phased implementation plan for `soliplex_sql`, an adapter that integrates [sql-toolset-pydantic-ai](https://github.com/vstorm-co/sql-toolset-pydantic-ai) (dev branch) into the Soliplex framework. The adapter wraps the upstream SQL tools to work with Soliplex's agent architecture, AG-UI protocol, and configuration system.

## Upstream Library Overview

The `sql-toolset-pydantic-ai` library provides:

| Tool | Description |
|------|-------------|
| `list_tables` | List all tables in the database |
| `get_schema` | Get database schema overview |
| `describe_table` | Get detailed table information |
| `explain_query` | Get query execution plan |
| `query` | Execute SQL queries with limits |
| `sample_query` | Quick data exploration |

**Key Components:**
- `SQLDatabaseProtocol`: Abstract protocol for database backends
- `SQLiteDatabase` / `PostgreSQLDatabase`: Backend implementations
- `SQLDatabaseDeps`: Configuration container (read_only, max_rows, timeout)
- `create_database_toolset()`: Factory creating PydanticAI FunctionToolset

---

## Phase 1: Project Foundation & Upstream Integration (Week 1-2)

### Objectives
- Establish project structure following soliplex patterns
- Integrate sql-toolset-pydantic-ai as dependency
- Create Soliplex-compatible configuration wrapper
- Set up development tooling (ruff, pytest, coverage)

### 1.1 Project Structure

```
soliplex_sql/
├── src/
│   └── soliplex_sql/
│       ├── __init__.py           # Public exports
│       ├── config.py             # Soliplex ToolConfig integration
│       ├── adapter.py            # Core adapter wrapping upstream tools
│       ├── tools.py              # Soliplex-compatible tool functions
│       ├── models.py             # Extended Pydantic models (if needed)
│       └── exceptions.py         # Soliplex-specific exceptions
├── tests/
│   ├── unit/
│   │   ├── conftest.py
│   │   ├── test_config.py
│   │   ├── test_adapter.py
│   │   └── test_tools.py
│   └── functional/
│       ├── conftest.py
│       └── test_soliplex_integration.py
├── pyproject.toml
├── README.md
├── LICENSE
├── PLAN_SQLTOOLS.md
└── ANALYSIS_SQLTOOLS.md
```

### 1.2 pyproject.toml

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "soliplex-sql"
version = "0.1.0dev0"
description = "Soliplex adapter for sql-toolset-pydantic-ai"
authors = [{ name = "runyaga", email = "runyaga@gmail.com" }]
readme = "README.md"
requires-python = ">=3.12"
classifiers = [
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "License :: OSI Approved :: MIT License",
]
dependencies = [
    # Upstream library (dev branch)
    "sql-toolset-pydantic-ai @ git+https://github.com/vstorm-co/sql-toolset-pydantic-ai.git@dev",
    # Soliplex core (for types/protocols)
    "pydantic >= 2.0.0",
    "pydantic-settings >= 2.0.0",
    "pydantic-ai >= 0.1.0",
]

[project.optional-dependencies]
soliplex = [
    # Full soliplex integration
    "soliplex",
]

[dependency-groups]
dev = [
    "pytest >= 8.0.0",
    "pytest-cov >= 4.0.0",
    "pytest-asyncio >= 0.23.0",
    "coverage >= 7.0.0",
    "ruff >= 0.4.0",
]

[tool.pytest.ini_options]
pythonpath = "src"
python_files = "test_*.py"
testpaths = ["tests/unit"]
asyncio_mode = "auto"
addopts = "--cov=soliplex_sql --cov-branch --cov-fail-under=95"

[tool.coverage.run]
source = ["src/soliplex_sql"]

[tool.coverage.report]
show_missing = true

[tool.ruff]
line-length = 79
target-version = "py312"

[tool.ruff.lint]
select = ["F", "E", "B", "UP", "I", "TRY", "PT", "SIM", "RUF"]

[tool.ruff.lint.isort]
force-single-line = true
```

### 1.3 Configuration Module (`src/soliplex_sql/config.py`)

```python
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
from sql_toolset_pydantic_ai import SQLDatabaseDeps
from sql_toolset_pydantic_ai import SQLiteDatabase
from sql_toolset_pydantic_ai import PostgreSQLDatabase

if TYPE_CHECKING:
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
    """Create appropriate backend from database URL."""
    if database_url.startswith("sqlite"):
        # Extract path from sqlite:///path.db
        path = database_url.replace("sqlite:///", "")
        return SQLiteDatabase(path)
    elif database_url.startswith("postgresql"):
        return PostgreSQLDatabase(database_url)
    else:
        raise ValueError(f"Unsupported database URL: {database_url}")


# Load environment variables at module level (fallback defaults)
_env_settings = SQLToolSettings()


@dataclasses.dataclass
class SQLToolConfigBase:
    """Base configuration for SQL tools.

    Soliplex requires 1:1 mapping between tool_name and config class.
    Each tool gets a subclass with its specific tool_name.

    Defaults come from environment variables via SQLToolSettings.
    Room configs can override any setting.

    Example room_config.yaml:
        tools:
          - tool_name: soliplex_sql.tools.list_tables
            database_url: sqlite:///./data.db
          - tool_name: soliplex_sql.tools.query
            database_url: postgresql://user:pass@host/db
    """

    # Defaults from environment variables (SOLIPLEX_SQL_*)
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

    # Soliplex integration
    agui_feature_names: tuple[str, ...] = ()

    # Set by from_yaml
    _installation_config: Any = dataclasses.field(default=None, repr=False)
    _config_path: pathlib.Path | None = None

    @classmethod
    def from_yaml(
        cls,
        installation_config: Any,
        config_path: pathlib.Path,
        config: dict[str, Any],
    ) -> SQLToolConfigBase:
        """Create from Soliplex YAML configuration."""
        config["_installation_config"] = installation_config
        config["_config_path"] = config_path
        return cls(**config)

    @property
    def kind(self) -> str:
        """Tool kind identifier (shared across all SQL tools)."""
        return "sql"

    def create_deps(self) -> SQLDatabaseDeps:
        """Create SQLDatabaseDeps from this configuration."""
        backend = _create_backend(self.database_url)
        return SQLDatabaseDeps(
            database=backend,
            read_only=self.read_only,
            max_rows=self.max_rows,
            query_timeout=self.query_timeout,
        )


# Per-tool config classes (Soliplex 1:1 mapping requirement)
@dataclasses.dataclass
class ListTablesConfig(SQLToolConfigBase):
    tool_name: str = "soliplex_sql.tools.list_tables"


@dataclasses.dataclass
class GetSchemaConfig(SQLToolConfigBase):
    tool_name: str = "soliplex_sql.tools.get_schema"


@dataclasses.dataclass
class DescribeTableConfig(SQLToolConfigBase):
    tool_name: str = "soliplex_sql.tools.describe_table"


@dataclasses.dataclass
class QueryConfig(SQLToolConfigBase):
    tool_name: str = "soliplex_sql.tools.query"


@dataclasses.dataclass
class ExplainQueryConfig(SQLToolConfigBase):
    tool_name: str = "soliplex_sql.tools.explain_query"


@dataclasses.dataclass
class SampleQueryConfig(SQLToolConfigBase):
    tool_name: str = "soliplex_sql.tools.sample_query"
```

### 1.4 Unit Tests for Phase 1

#### test_config.py

```python
"""Tests for configuration module."""

from __future__ import annotations

import pytest

from soliplex_sql.config import SQLToolConfig
from soliplex_sql.config import SQLToolSettings
from soliplex_sql.config import _create_backend


class TestSQLToolSettings:
    """Tests for environment-based settings."""

    def test_default_values(self):
        """Default settings should be valid."""
        settings = SQLToolSettings()

        assert settings.read_only is True
        assert settings.max_rows == 100
        assert settings.query_timeout == 30.0

    def test_env_override(self, monkeypatch):
        """Environment variables override defaults."""
        monkeypatch.setenv("SOLIPLEX_SQL_READ_ONLY", "false")
        monkeypatch.setenv("SOLIPLEX_SQL_MAX_ROWS", "500")

        settings = SQLToolSettings()

        assert settings.read_only is False
        assert settings.max_rows == 500


class TestCreateBackend:
    """Tests for backend factory."""

    def test_sqlite_backend(self):
        """Should create SQLite backend."""
        backend = _create_backend("sqlite:///./test.db")
        assert backend is not None

    def test_unsupported_raises(self):
        """Should raise for unsupported URLs."""
        with pytest.raises(ValueError, match="Unsupported"):
            _create_backend("mysql://localhost/db")


class TestSQLToolConfig:
    """Tests for Soliplex ToolConfig integration."""

    def test_from_yaml(self):
        """Should create from YAML config dict."""
        config = SQLToolConfig.from_yaml(
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

    def test_create_deps(self):
        """Should create SQLDatabaseDeps."""
        config = SQLToolConfig(
            database_url="sqlite:///./test.db",
            read_only=True,
            max_rows=50,
        )

        deps = config.create_deps()

        assert deps.read_only is True
        assert deps.max_rows == 50
```

### 1.5 Gate Criteria - Phase 1

| Criterion | Target | Verification |
|-----------|--------|--------------|
| Project structure | Complete | Directory layout matches spec |
| pyproject.toml | Valid | `pip install -e .` succeeds |
| Upstream integration | Working | `from sql_toolset_pydantic_ai import *` works |
| Ruff lint | 0 errors | `ruff check src tests` passes |
| Unit tests | Pass | `pytest tests/unit` passes |
| Coverage | ≥95% | Coverage target maintained |

---

## Phase 2: Soliplex Tool Wrappers (Week 3-4)

### Objectives
- Wrap upstream tools with Soliplex AgentDependencies context
- Add AG-UI StateDeltaEvent emission for task progress
- Integrate with Soliplex's tool registration system

### 2.1 Adapter Module (`src/soliplex_sql/adapter.py`)

```python
"""Core adapter bridging sql-toolset-pydantic-ai with Soliplex.

NOTE: This adapter calls the upstream database backend directly rather than
using create_database_toolset(). This avoids unnecessary FunctionToolset
overhead and gives us full control over AG-UI event emission.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING
from typing import Any

from sql_toolset_pydantic_ai import SQLDatabaseDeps

if TYPE_CHECKING:
    from soliplex.agents import AgentDependencies
    from soliplex.agui.events import StateDeltaEvent


def _create_task_status_patch(
    task_id: str,
    status: str,
    result: str | None = None,
) -> list[dict]:
    """Create JSON Patch operations for task status update.

    Follows Soliplex convention from soliplex.tools module.
    """
    now = datetime.datetime.now(datetime.UTC).isoformat()
    patches = [
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
        patches.append({
            "op": "replace",
            "path": f"/task_list/tasks/{task_id}/result",
            "value": result,
        })
    return patches


class SoliplexSQLAdapter:
    """Adapter wrapping sql-toolset-pydantic-ai for Soliplex.

    Provides:
    - AG-UI state delta events for task progress
    - Integration with Soliplex AgentDependencies
    - Soliplex ToolConfig compatibility

    NOTE: Calls backend directly, not via create_database_toolset().
    """

    def __init__(self, sql_deps: SQLDatabaseDeps):
        self._sql_deps = sql_deps
        # Direct backend access - no FunctionToolset overhead

    def _emit_task_progress(
        self,
        soliplex_deps: AgentDependencies,
        task_id: str | None,
        status: str,
        result: str | None = None,
    ) -> None:
        """Emit AG-UI state delta for task progress."""
        if task_id is None:
            return

        from soliplex.agui.events import StateDeltaEvent

        event = StateDeltaEvent(
            delta=_create_task_status_patch(task_id, status, result)
        )
        soliplex_deps.agui_emitter.emit(event)

    async def list_tables(
        self,
        soliplex_deps: AgentDependencies,
        related_task_id: str | None = None,
    ) -> list[str]:
        """List all tables in the database.

        Wraps upstream list_tables with Soliplex task progress.
        """
        self._emit_task_progress(
            soliplex_deps, related_task_id, "in_progress"
        )

        try:
            tables = await self._sql_deps.database.get_tables()

            self._emit_task_progress(
                soliplex_deps,
                related_task_id,
                "completed",
                f"Found {len(tables)} tables",
            )
            return tables

        except Exception as e:
            self._emit_task_progress(
                soliplex_deps,
                related_task_id,
                "in_progress",
                f"Error: {e}",
            )
            raise

    async def get_schema(
        self,
        soliplex_deps: AgentDependencies,
        related_task_id: str | None = None,
    ) -> dict[str, Any]:
        """Get database schema overview."""
        self._emit_task_progress(
            soliplex_deps, related_task_id, "in_progress"
        )

        try:
            schema = await self._sql_deps.database.get_schema()

            self._emit_task_progress(
                soliplex_deps,
                related_task_id,
                "completed",
                f"Retrieved schema with {len(schema.tables)} tables",
            )

            # Convert to dict for JSON serialization
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
                soliplex_deps,
                related_task_id,
                "in_progress",
                f"Error: {e}",
            )
            raise

    # ... additional wrapped methods for describe_table, query, etc.
```

### 2.2 Tools Module (`src/soliplex_sql/tools.py`)

```python
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

import pydantic_ai

from soliplex_sql.adapter import SoliplexSQLAdapter
from soliplex_sql.config import SQLToolConfig
from soliplex_sql.config import SQLToolSettings

if TYPE_CHECKING:
    from soliplex.agents import AgentDependencies

# Module-level cache: config_hash -> adapter (supports concurrent rooms)
_adapter_cache: dict[int, SoliplexSQLAdapter] = {}


def _get_adapter(
    ctx: pydantic_ai.RunContext[AgentDependencies],
) -> SoliplexSQLAdapter:
    """Get or create SQL adapter from context.

    Uses dict-based caching to support multiple concurrent database
    connections (e.g., Room A -> Sales DB, Room B -> HR DB).
    Critical for PostgreSQL connection pooling performance.
    """
    # Get config from tool_configs (per-tool subclass provides settings)
    tool_configs = ctx.deps.tool_configs
    tool_config: SQLToolConfigBase | None = None

    # Look for any SQL tool config (they share 'kind')
    for config in tool_configs.values():
        if hasattr(config, 'kind') and config.kind == "sql":
            tool_config = config
            break

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
    config_hash = hash((
        tool_config.database_url,
        tool_config.read_only,
        tool_config.max_rows,
    ))

    # Check cache dict (supports multiple DBs concurrently)
    if config_hash in _adapter_cache:
        return _adapter_cache[config_hash]

    # Create new adapter and cache it
    sql_deps = tool_config.create_deps()
    adapter = SoliplexSQLAdapter(sql_deps)
    _adapter_cache[config_hash] = adapter

    return adapter


async def list_tables(
    ctx: pydantic_ai.RunContext[AgentDependencies],
    related_task_id: str | None = None,
) -> list[str]:
    """List all tables in the database.

    Args:
        related_task_id: Optional task ID to update with progress

    Returns:
        List of table names
    """
    adapter = _get_adapter(ctx)
    return await adapter.list_tables(ctx.deps, related_task_id)


async def get_schema(
    ctx: pydantic_ai.RunContext[AgentDependencies],
    related_task_id: str | None = None,
) -> dict[str, Any]:
    """Get database schema overview.

    Args:
        related_task_id: Optional task ID to update with progress

    Returns:
        Schema information with tables, columns, and row counts
    """
    adapter = _get_adapter(ctx)
    return await adapter.get_schema(ctx.deps, related_task_id)


async def describe_table(
    ctx: pydantic_ai.RunContext[AgentDependencies],
    table_name: str,
    related_task_id: str | None = None,
) -> dict[str, Any] | None:
    """Get detailed information about a specific table.

    Args:
        table_name: Name of the table to describe
        related_task_id: Optional task ID to update with progress

    Returns:
        Table information including columns, types, constraints
    """
    adapter = _get_adapter(ctx)
    return await adapter.describe_table(ctx.deps, table_name, related_task_id)


async def query(
    ctx: pydantic_ai.RunContext[AgentDependencies],
    sql_query: str,
    max_rows: int | None = None,
    related_task_id: str | None = None,
) -> dict[str, Any]:
    """Execute a SQL query and return results.

    Args:
        sql_query: SQL query to execute
        max_rows: Maximum rows to return (optional)
        related_task_id: Optional task ID to update with progress

    Returns:
        Query results with columns, rows, and metadata
    """
    adapter = _get_adapter(ctx)
    return await adapter.query(
        ctx.deps, sql_query, max_rows, related_task_id
    )


async def explain_query(
    ctx: pydantic_ai.RunContext[AgentDependencies],
    sql_query: str,
    related_task_id: str | None = None,
) -> str:
    """Get the execution plan for a SQL query.

    Args:
        sql_query: SQL query to analyze
        related_task_id: Optional task ID to update with progress

    Returns:
        Query execution plan
    """
    adapter = _get_adapter(ctx)
    return await adapter.explain_query(ctx.deps, sql_query, related_task_id)


async def sample_query(
    ctx: pydantic_ai.RunContext[AgentDependencies],
    sql_query: str,
    limit: int = 5,
    related_task_id: str | None = None,
) -> dict[str, Any]:
    """Execute a sample query for quick data exploration.

    Args:
        sql_query: SQL query to execute
        limit: Maximum rows (default: 5)
        related_task_id: Optional task ID to update with progress

    Returns:
        Sample query results
    """
    adapter = _get_adapter(ctx)
    return await adapter.sample_query(
        ctx.deps, sql_query, limit, related_task_id
    )
```

### 2.3 Unit Tests for Phase 2

#### test_tools.py (Unit tests with mocks)

```python
"""Unit tests for Soliplex-compatible tools."""

from __future__ import annotations

from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from soliplex_sql.config import SQLToolConfig


@pytest.fixture
def mock_deps():
    """Create mock AgentDependencies."""
    deps = MagicMock()
    deps.tool_configs = {
        "sql": SQLToolConfig(database_url="sqlite:///:memory:"),
    }
    deps.agui_emitter = MagicMock()
    deps.agui_emitter.emit = MagicMock()
    return deps


@pytest.fixture
def mock_ctx(mock_deps):
    """Create mock RunContext."""
    ctx = MagicMock()
    ctx.deps = mock_deps
    return ctx


class TestAGUIEvents:
    """Tests for AG-UI event emission."""

    async def test_emits_in_progress_on_start(self, mock_ctx):
        """Should emit in_progress when task_id provided."""
        pass

    async def test_emits_completed_on_success(self, mock_ctx):
        """Should emit completed on successful operation."""
        pass

    async def test_no_events_without_task_id(self, mock_ctx):
        """Should not emit events when task_id is None."""
        pass
```

#### test_tools_integration.py (Real database tests)

```python
"""Integration tests with real SQLite database.

IMPORTANT: These tests use actual SQLite files to catch real
SQL dialect issues and connection problems that mocks would miss.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from soliplex_sql.adapter import SoliplexSQLAdapter
from soliplex_sql.config import SQLToolConfig


@pytest.fixture
async def real_db():
    """Create real SQLite database with test data."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    config = SQLToolConfig(
        database_url=f"sqlite:///{db_path}",
        read_only=False,
    )
    deps = config.create_deps()

    # Connect and create test table
    await deps.database.connect()

    await deps.database.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE
        )
    """)

    await deps.database.execute("""
        INSERT INTO users (name, email) VALUES
        ('Alice', 'alice@test.com'),
        ('Bob', 'bob@test.com')
    """)

    yield deps

    await deps.database.close()
    Path(db_path).unlink(missing_ok=True)


class TestRealDatabase:
    """Integration tests against real SQLite."""

    async def test_list_tables_returns_created_table(self, real_db):
        """Should list tables from real database."""
        tables = await real_db.database.get_tables()
        assert "users" in tables

    async def test_get_schema_includes_columns(self, real_db):
        """Should return schema with column info."""
        schema = await real_db.database.get_schema()
        users_table = next(t for t in schema.tables if t.name == "users")
        column_names = [c.name for c in users_table.columns]
        assert "id" in column_names
        assert "name" in column_names

    async def test_query_returns_inserted_data(self, real_db):
        """Should query real data."""
        result = await real_db.database.execute(
            "SELECT name FROM users ORDER BY name"
        )
        assert result.row_count == 2
        assert result.rows[0][0] == "Alice"

    async def test_read_only_blocks_mutations(self, real_db):
        """Should block INSERT/UPDATE/DELETE in read_only mode."""
        # Recreate with read_only=True
        # Verify mutations are blocked
        pass
```

### 2.4 Gate Criteria - Phase 2

| Criterion | Target | Verification |
|-----------|--------|--------------|
| Tool wrappers | Complete | All 6 upstream tools wrapped |
| AG-UI events | Working | StateDeltaEvent emitted for tasks |
| Context integration | Working | Tools access AgentDependencies |
| ToolConfig | Working | Configuration from YAML works |
| Unit tests | Pass | All tool tests pass |
| Coverage | ≥95% | Coverage target maintained |

---

## Phase 3: Room Configuration Integration (Week 5-6)

### Objectives
- Register SQLToolConfig with Soliplex config system
- Create example room configuration
- Add MCP server mode (standalone operation)
- Integration testing with Soliplex

### 3.1 Registration (`src/soliplex_sql/__init__.py`)

```python
"""Soliplex SQL Adapter.

Integrates sql-toolset-pydantic-ai into the Soliplex framework.
"""

from __future__ import annotations

from importlib.metadata import version

# Configuration
from soliplex_sql.config import SQLToolConfig
from soliplex_sql.config import SQLToolSettings

# Tools (for direct import in room configs)
from soliplex_sql.tools import describe_table
from soliplex_sql.tools import explain_query
from soliplex_sql.tools import get_schema
from soliplex_sql.tools import list_tables
from soliplex_sql.tools import query
from soliplex_sql.tools import sample_query

__all__ = [
    # Configuration
    "SQLToolConfig",
    "SQLToolSettings",
    # Tools
    "list_tables",
    "get_schema",
    "describe_table",
    "explain_query",
    "query",
    "sample_query",
]

__version__ = version("soliplex-sql")
```

### 3.2 Configuration Approach

**IMPORTANT**: Soliplex RoomConfig does not support arbitrary top-level keys.
Use environment variables for database configuration:

```bash
# Environment variables (recommended)
export SOLIPLEX_SQL_DATABASE_URL="sqlite:///./data.db"
export SOLIPLEX_SQL_READ_ONLY="true"
export SOLIPLEX_SQL_MAX_ROWS="100"
export SOLIPLEX_SQL_QUERY_TIMEOUT="30.0"
```

### 3.3 Example Room Configuration

```yaml
# example/rooms/sql-assistant/room_config.yaml
id: sql-assistant
name: SQL Database Assistant
description: Query and explore your database with AI assistance

agent:
  model_name: qwen3-coder-tools:30b
  system_prompt: |
    You are a helpful database assistant. You can:
    - List and describe database tables
    - Execute SQL queries
    - Explain query plans
    - Help users understand their data

    Always use the SQL tools to interact with the database.
    Be careful with data - the database may be in read-only mode.

# All SQL tools share configuration via environment variables
tools:
  - tool_name: soliplex_sql.tools.list_tables
  - tool_name: soliplex_sql.tools.get_schema
  - tool_name: soliplex_sql.tools.describe_table
  - tool_name: soliplex_sql.tools.query
  - tool_name: soliplex_sql.tools.explain_query
  - tool_name: soliplex_sql.tools.sample_query

suggestions:
  - "What tables are in the database?"
  - "Describe the users table"
  - "Show me a sample of the orders data"
```

### 3.5 Installation Registration

Register ALL SQL tool config classes (Soliplex 1:1 mapping requirement):

```yaml
# installation.yaml
meta:
  tool_configs:
    - soliplex_sql.config.ListTablesConfig
    - soliplex_sql.config.GetSchemaConfig
    - soliplex_sql.config.DescribeTableConfig
    - soliplex_sql.config.QueryConfig
    - soliplex_sql.config.ExplainQueryConfig
    - soliplex_sql.config.SampleQueryConfig
```

### 3.6 Per-Room Database Configuration

Rooms can override database settings (environment vars are fallback):

```yaml
# room_config.yaml for Sales team
tools:
  - tool_name: soliplex_sql.tools.query
    database_url: postgresql://user:pass@db-host/sales_db
    read_only: true
    max_rows: 500
```

```yaml
# room_config.yaml for HR team
tools:
  - tool_name: soliplex_sql.tools.query
    database_url: postgresql://user:pass@db-host/hr_db
    read_only: true
```

### 3.3 Gate Criteria - Phase 3

| Criterion | Target | Verification |
|-----------|--------|--------------|
| Config registration | Working | SQLToolConfig loads from YAML |
| Example room | Complete | room_config.yaml provided |
| Tools callable | Working | All tools work from room config |
| Integration tests | Pass | End-to-end test with Soliplex |
| Documentation | Updated | README reflects room usage |

---

## Phase 4: Polish & Release (Week 7-8)

### Objectives
- Complete documentation
- Add comprehensive error handling
- Performance testing
- Release preparation

### 4.1 Final Checklist

| Item | Status | Notes |
|------|--------|-------|
| README.md | | Complete documentation |
| CONTRIBUTING.md | | Development guide |
| LICENSE | | MIT license |
| pyproject.toml | | All metadata |
| Type hints | | 100% coverage |
| Docstrings | | All public APIs |
| Unit tests | | ≥95% coverage |
| Functional tests | | Integration verified |
| Ruff lint | | 0 errors |
| Example room | | Working configuration |

### 4.2 Gate Criteria - Phase 4 (Final)

| Criterion | Target | Verification |
|-----------|--------|--------------|
| All tests pass | Yes | `pytest` succeeds |
| Coverage ≥95% | Yes | `--cov-fail-under=95` |
| Ruff clean | Yes | `ruff check` passes |
| Documentation | Complete | README covers all features |
| Example works | Yes | Room config functional |
| Package builds | Yes | `pip install .` succeeds |

---

## Summary

| Phase | Duration | Key Deliverables |
|-------|----------|-----------------|
| 1. Foundation | Week 1-2 | Project setup, upstream integration, config |
| 2. Tool Wrappers | Week 3-4 | Soliplex-compatible tools with AG-UI events |
| 3. Room Integration | Week 5-6 | Full Soliplex configuration support |
| 4. Polish | Week 7-8 | Documentation, testing, release |

### Dependencies

**Runtime:**
- sql-toolset-pydantic-ai (dev branch)
- pydantic >= 2.0.0
- pydantic-ai >= 0.1.0
- soliplex (optional, for full integration)

**Development:**
- pytest, pytest-asyncio, pytest-cov
- ruff
- coverage

### Risk Mitigation

1. **Upstream changes**: Pin to specific commit hash if needed
2. **API compatibility**: Adapter pattern isolates changes
3. **Testing**: High coverage ensures regressions caught early
