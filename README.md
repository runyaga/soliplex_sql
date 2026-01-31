# soliplex_sql

**SQL Tools MCP Server** - A Model Context Protocol (MCP) server providing SQL database tools for AI assistants.

## Overview

`soliplex_sql` is an MCP server that exposes SQL database operations as tools for AI assistants. It enables LLMs to interact with SQL databases through a well-defined, type-safe interface with proper schema discovery, query execution, and result formatting.

## Features

- **Schema Discovery**: Introspect database schemas, tables, columns, and relationships
- **Query Execution**: Execute SELECT queries with parameterized inputs
- **Write Operations**: INSERT, UPDATE, DELETE with transaction support
- **Query Building**: Structured query builder for safe SQL generation
- **Connection Pooling**: Efficient async connection management
- **Multi-Database Support**: SQLite, PostgreSQL, MySQL (via SQLAlchemy)

## Tech Stack

- **Python 3.12+**
- **FastMCP**: MCP server framework
- **SQLAlchemy 2.x**: Async database operations
- **Pydantic**: Data validation and serialization
- **aiosqlite/asyncpg**: Async database drivers

## Installation

```bash
pip install soliplex-sql
```

Or for development:

```bash
git clone https://github.com/runyaga/soliplex_sql.git
cd soliplex_sql
pip install -e ".[dev]"
```

## Quick Start

### As MCP Server

```python
from soliplex_sql import create_mcp_server

server = create_mcp_server(
    database_url="sqlite+aiosqlite:///./data.db"
)
server.run()
```

### Configuration

Configure via environment variables:

```bash
export SOLIPLEX_SQL_DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db"
export SOLIPLEX_SQL_POOL_SIZE=10
export SOLIPLEX_SQL_MAX_OVERFLOW=20
```

## Available Tools

| Tool | Description |
|------|-------------|
| `list_tables` | List all tables in the database |
| `describe_table` | Get schema info for a table |
| `execute_query` | Execute a SELECT query |
| `insert_row` | Insert a new row |
| `update_rows` | Update rows matching criteria |
| `delete_rows` | Delete rows matching criteria |

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run linter
ruff check src tests

# Run formatter
ruff format src tests

# Run tests
pytest

# Run tests with coverage
pytest --cov=soliplex_sql --cov-report=html
```

## Code Quality Standards

This project follows the code quality standards from [soliplex](https://github.com/runyaga/soliplex):

- **Ruff** for linting and formatting (line-length: 79)
- **Type hints** on all functions
- **Pydantic models** for all data structures
- **Async/await** for all I/O operations
- **100% test coverage** target

## License

MIT License - see [LICENSE](LICENSE) for details.
