# soliplex_sql

**Soliplex SQL Adapter** - Integration of [sql-toolset-pydantic-ai](https://github.com/vstorm-co/sql-toolset-pydantic-ai) (dev branch) into the Soliplex framework.

## Overview

`soliplex_sql` adapts the `sql-toolset-pydantic-ai` library for use within the [Soliplex](https://github.com/runyaga/soliplex) ecosystem. It bridges SQL database tools with Soliplex's agent architecture, enabling AI assistants to interact with SQL databases.

## Purpose

This adapter provides:

- **Soliplex Integration**: Wraps sql-toolset-pydantic-ai tools for Soliplex agent dependencies
- **Room Configuration**: Exposes SQL tools as configurable room tools in Soliplex installations
- **Per-Room Databases**: Each room can connect to a different database
- **Connection Pooling**: Adapters are cached per-configuration for efficiency

## Tech Stack

- Python 3.12+
- pydantic-ai (via soliplex)
- sql-toolset-pydantic-ai (upstream SQL tools)
- SQLAlchemy 2.x (async database operations)
- Pydantic (data validation)

## Installation

```bash
pip install soliplex-sql
```

For development:

```bash
git clone https://github.com/runyaga/soliplex_sql.git
cd soliplex_sql
pip install -e ".[dev]"
```

## Usage

### Step 1: Register Tool Configs

Add to your `installation.yaml`:

```yaml
meta:
  tool_configs:
    - soliplex_sql.config.ListTablesConfig
    - soliplex_sql.config.GetSchemaConfig
    - soliplex_sql.config.DescribeTableConfig
    - soliplex_sql.config.QueryConfig
    - soliplex_sql.config.ExplainQueryConfig
    - soliplex_sql.config.SampleQueryConfig
```

### Step 2: Configure Database

Set environment variables (default for all rooms):

```bash
export SOLIPLEX_SQL_DATABASE_URL="sqlite:///./data.db"
export SOLIPLEX_SQL_READ_ONLY="true"
export SOLIPLEX_SQL_MAX_ROWS="100"
export SOLIPLEX_SQL_QUERY_TIMEOUT="30.0"
```

### Step 3: Create Room Configuration

Basic room using environment defaults:

```yaml
# room_config.yaml
id: sql-assistant
name: SQL Database Assistant

agent:
  model_name: qwen3-coder-tools:30b
  system_prompt: You are a database assistant.

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
```

### Per-Room Database Configuration

Override database settings for specific rooms. **Note:** Each tool must be listed explicitly with its configuration.

```yaml
# rooms/sales-db/room_config.yaml
id: sales-db
name: Sales Database

tools:
  # Each tool needs explicit database_url if overriding
  - tool_name: soliplex_sql.tools.list_tables
    database_url: "sqlite:///./sales.db"
    read_only: true
  - tool_name: soliplex_sql.tools.query
    database_url: "sqlite:///./sales.db"
    read_only: true
    max_rows: 500
  - tool_name: soliplex_sql.tools.describe_table
    database_url: "sqlite:///./sales.db"
```

```yaml
# rooms/hr-db/room_config.yaml
id: hr-db
name: HR Database

tools:
  - tool_name: soliplex_sql.tools.list_tables
    database_url: "sqlite:///./hr.db"
  - tool_name: soliplex_sql.tools.query
    database_url: "sqlite:///./hr.db"
    read_only: true
    max_rows: 100
```

Each room can connect to a different database. Adapters are cached per-configuration for connection pooling efficiency.

**Security Note:** Avoid committing database credentials to version control. Use environment variables for sensitive connection strings.

### Example Room

See `example/rooms/sql-assistant/` for a complete working example.

## Available Tools

| Tool | Description |
|------|-------------|
| `list_tables` | List all tables in the database |
| `get_schema` | Get database schema overview |
| `describe_table` | Get detailed table information |
| `explain_query` | Get query execution plan |
| `query` | Execute SQL queries with limits |
| `sample_query` | Quick data exploration |

## Development

```bash
pip install -e ".[dev]"
ruff check src tests
ruff format src tests
pytest
pytest --cov=soliplex_sql --cov-report=html
```

## Code Quality Standards

Follows [soliplex](https://github.com/runyaga/soliplex) standards:

- Ruff for linting/formatting (line-length: 79)
- Type hints on all functions
- Pydantic models for data structures
- Async/await for I/O operations
- 95%+ test coverage target

Additionally follows:

- **pydantic-ai idioms**: RunContext dependency injection, async tool functions
- **Soliplex framework integration**: ToolConfig registration, per-room configuration

## Related Projects

- [soliplex](https://github.com/runyaga/soliplex) - Parent framework
- [sql-toolset-pydantic-ai](https://github.com/vstorm-co/sql-toolset-pydantic-ai) - Upstream SQL tools

## License

MIT License - see [LICENSE](LICENSE) for details.
