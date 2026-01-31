# Contributing to soliplex_sql

Thank you for your interest in contributing to soliplex_sql!

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/runyaga/soliplex_sql.git
   cd soliplex_sql
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   ```

3. Verify setup:
   ```bash
   ruff check src tests
   pytest
   ```

## Code Standards

### Formatting & Linting

We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
# Check for issues
ruff check src tests

# Auto-fix fixable issues
ruff check --fix src tests

# Format code
ruff format src tests
```

Configuration in `pyproject.toml`:
- Line length: 79 characters
- Target: Python 3.12+

### Type Hints

All functions must have type hints:

```python
async def query(
    ctx: RunContext[AgentDependencies],
    sql_query: str,
    max_rows: int | None = None,
) -> dict[str, Any]:
    ...
```

### Testing

Run tests with pytest:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=soliplex_sql --cov-report=html

# Run specific test file
pytest tests/unit/test_config.py

# Run with verbose output
pytest -v
```

Test coverage target: **95%+**

### Test Categories

- `tests/unit/` - Unit tests with mocks
- `tests/functional/` - Tests with real SQLite databases
- `tests/integration/` - End-to-end tests (require running server)

## Pull Request Process

1. Create a feature branch:
   ```bash
   git checkout -b feat/your-feature
   ```

2. Make your changes following the code standards above

3. Ensure all checks pass:
   ```bash
   ruff check src tests
   pytest
   ```

4. Commit with conventional commit format:
   ```bash
   git commit -m "feat(scope): description"
   ```

   Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`

5. Push and create a PR:
   ```bash
   git push -u origin feat/your-feature
   ```

## Commit Message Format

```
<type>(<scope>): <description>

<body - what changed and why>
```

Examples:
- `feat(tools): Add new sample_query tool`
- `fix(config): Handle missing database_url gracefully`
- `test(adapter): Add read-only mode tests`
- `docs(readme): Update installation instructions`

## Architecture Overview

```
src/soliplex_sql/
├── __init__.py      # Public exports
├── config.py        # ToolConfig classes for Soliplex
├── adapter.py       # SoliplexSQLAdapter wrapping upstream
├── tools.py         # Tool functions with caching
└── exceptions.py    # Custom exception hierarchy
```

Key concepts:
- **Adapter pattern**: Wraps sql-toolset-pydantic-ai for Soliplex
- **Per-tool configs**: Each tool has its own config class
- **Adapter caching**: Connections cached by config tuple
- **Read-only enforcement**: SQL prefix validation

## Questions?

Open an issue on GitHub for questions or discussions.
