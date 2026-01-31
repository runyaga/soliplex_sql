# soliplex_sql

**Soliplex SQL Adapter** - Integration of [sql-toolset-pydantic-ai](https://github.com/vstorm-co/sql-toolset-pydantic-ai) (dev branch) into the Soliplex framework.

## Overview

`soliplex_sql` adapts the `sql-toolset-pydantic-ai` library for use within the [Soliplex](https://github.com/runyaga/soliplex) ecosystem. It bridges SQL database tools with Soliplex's agent architecture, enabling AI assistants to interact with SQL databases through the AG-UI protocol.

## Purpose

This adapter provides:

- **Soliplex Integration**: Wraps sql-toolset-pydantic-ai tools for Soliplex agent dependencies
- **AG-UI Compatibility**: Emits state events and progress updates compatible with Soliplex clients
- **Room Configuration**: Exposes SQL tools as configurable room tools in Soliplex installations
- **MCP Server Mode**: Can also run as a standalone MCP server

See [docs/architecture.md](docs/architecture.md) for visual architecture diagram.

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

### As Soliplex Room Tool

Configure in your Soliplex room configuration:

```yaml
# room_config.yaml
id: sql-assistant
name: SQL Assistant

agent:
  model_name: qwen3-coder-tools:30b
  system_prompt: You are a database assistant.

tools:
  - tool_name: soliplex_sql.tools.list_tables
  - tool_name: soliplex_sql.tools.query
  - tool_name: soliplex_sql.tools.describe_table
```

Configure database via environment variables:

```bash
export SOLIPLEX_SQL_DATABASE_URL="sqlite:///./data.db"
export SOLIPLEX_SQL_READ_ONLY="true"
export SOLIPLEX_SQL_MAX_ROWS="100"
```

### As Standalone MCP Server

```bash
export SOLIPLEX_SQL_DATABASE_URL="sqlite:///./data.db"
soliplex-sql serve
```

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

- **pydantic-ai idioms**: RunContext, FunctionToolset patterns, dependency injection
- **Soliplex framework integration**: AG-UI events, ToolConfig registration, StateDeltaEvent emission for task progress

## Related Projects

- [soliplex](https://github.com/runyaga/soliplex) - Parent framework
- [sql-toolset-pydantic-ai](https://github.com/vstorm-co/sql-toolset-pydantic-ai) - Upstream SQL tools

## License

MIT License - see [LICENSE](LICENSE) for details.
