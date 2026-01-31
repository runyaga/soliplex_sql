# Soliplex SQL Adapter - Analysis Document

## Overview

This document captures the analysis and review iterations for the `soliplex_sql` implementation plan. It serves as a record of design decisions, identified issues, and refinements made through the review process.

## Upstream Library Analysis

### sql-toolset-pydantic-ai (dev branch)

**Repository**: https://github.com/vstorm-co/sql-toolset-pydantic-ai

**Key Components Identified**:

1. **SQLDatabaseProtocol** (`sql/protocol.py`)
   - Abstract protocol defining database backend interface
   - Methods: `connect`, `close`, `execute`, `get_tables`, `get_foreign_keys`, `get_table_info`, `get_schema`, `explain`

2. **Backend Implementations** (`sql/backends/`)
   - `SQLiteDatabase`: aiosqlite-based SQLite backend
   - `PostgreSQLDatabase`: asyncpg-based PostgreSQL backend

3. **SQLDatabaseDeps** (`sql/toolset.py`)
   - Configuration container dataclass
   - Parameters: `database`, `read_only`, `max_rows`, `query_timeout`, `id`

4. **create_database_toolset()** (`sql/toolset.py`)
   - Factory creating PydanticAI FunctionToolset
   - Returns toolset with 6 tools registered

5. **Data Types** (`types.py`)
   - `QueryResult`: columns, rows, row_count, execution_time_ms
   - `TableInfo`: name, columns, row_count, primary_key, foreign_keys
   - `ColumnInfo`: name, data_type, nullable, default, is_primary_key
   - `ForeignKeyInfo`: column, references_table, references_column
   - `SchemaInfo`: tables, views

### Tool Signatures

| Tool | Arguments | Returns |
|------|-----------|---------|
| `list_tables` | ctx | `list[str]` |
| `get_schema` | ctx | `SchemaInfo` |
| `describe_table` | ctx, table_name | `TableInfo | None` |
| `explain_query` | ctx, sql_query | `str` |
| `query` | ctx, sql_query, max_rows? | `QueryResult` |
| `sample_query` | ctx, sql_query, limit=5 | `QueryResult` |

## Soliplex Integration Requirements

### AgentDependencies Context

From `soliplex.agents.AgentDependencies`:
- `agui_emitter`: AG-UI event emitter
- `tool_configs`: Dict of ToolConfig instances
- `state`: AGUI_State for current session
- `user`: UserProfile for current user

### Task Progress Pattern

From `soliplex.tools`:
- Tools should accept `related_task_id: str | None` parameter
- Emit `StateDeltaEvent` with JSON Patch for task updates
- Status values: "pending", "in_progress", "completed", "blocked", "skipped"

### ToolConfig Pattern

From `soliplex` room configuration:
- `tool_name`: Module path to tool function
- `@classmethod from_yaml()`: Factory for YAML config
- `kind`: Tool type identifier
- `tool_id`: Registration identifier

## Design Decisions

### D1: Adapter Pattern

**Decision**: Use adapter pattern to wrap upstream tools rather than forking.

**Rationale**:
- Maintains compatibility with upstream updates
- Clear separation between Soliplex and sql-toolset concerns
- Easier testing - can mock upstream components

### D2: Stateless Tool Functions

**Decision**: Create stateless tool functions that create adapter instances on each call.

**Rationale**:
- Follows Soliplex tool convention
- Avoids connection pooling complexity in adapter layer
- Configuration changes take effect immediately

### D3: Dict Return Types

**Decision**: Convert dataclass results to dicts for JSON serialization.

**Rationale**:
- AG-UI protocol expects JSON-serializable data
- Pydantic models in Soliplex use dict conversion
- Consistent with other Soliplex tools

### D4: Optional Soliplex Dependency

**Decision**: Make full Soliplex integration optional via extras.

**Rationale**:
- Allows testing without full Soliplex installation
- Tools can be used standalone or with Soliplex
- Gradual adoption path

## Risk Analysis

### R1: Upstream API Changes

**Risk**: sql-toolset-pydantic-ai may change APIs between versions.

**Mitigation**:
- Pin to specific commit hash in pyproject.toml
- Adapter pattern isolates changes
- Comprehensive tests catch breaking changes

### R2: Connection Management

**Risk**: Creating new database connections per tool call may impact performance.

**Mitigation**:
- Profile actual usage patterns
- Consider connection caching in adapter if needed
- Document connection lifecycle

### R3: Type Mismatch

**Risk**: Upstream types may not match Soliplex expectations.

**Mitigation**:
- Explicit conversion in adapter
- Pydantic validation on boundaries
- Test coverage for type conversions

## Review Iterations

### Iteration 1: Initial Review (Gemini gemini-3-pro-preview)

**Critical Issues Identified:**

1. **Invalid Room Config Schema**
   - The proposed `sql:` top-level key in room_config.yaml violates Soliplex RoomConfig schema
   - Soliplex config.py defines strict dataclass - unexpected keys raise `FromYamlException`
   - **Fix**: Use environment variables or tools list configuration, not custom YAML keys

2. **Missing ToolConfig Registration**
   - Simply exporting SQLToolConfig in `__init__.py` does not register it with Soliplex
   - Soliplex uses `TOOL_CONFIG_CLASSES_BY_TOOL_NAME` or `InstallationConfigMeta`
   - **Fix**: Document explicit registration in installation's `meta` section

3. **Database Connection Lifecycle (HIGH RISK)**
   - Current design creates new DB connection per tool invocation
   - For PostgreSQL this defeats connection pooling entirely
   - **Fix**: Cache SQLToolConfig/backend at Agent/Room scope, not per-call

4. **Unused Upstream Toolset**
   - Adapter creates `create_database_toolset()` but never uses it
   - Manually calls `self._sql_deps.database.get_tables()` instead
   - **Fix**: Remove unused toolset creation, call backend directly

5. **Kind Uniqueness Collision**
   - Multiple tools sharing `kind="sql"` collide in `tool_configs` dict
   - **Fix**: Single SQLToolConfig instance shared across all SQL tools

6. **Missing Real Integration Tests**
   - Plan relies on unittest.mock for DB - won't catch SQL dialect issues
   - **Fix**: Add tests against real SQLite file

### Iteration 2: Refinement (Gemini gemini-3-pro-preview)

**Verification of Iteration 1 Fixes:**
- Config Fixed: PARTIAL - env vars used but limits per-room flexibility
- Registration Documented: BROKEN - 1:1 tool_name mapping violated
- Connection Caching: PARTIAL - single var causes cache thrashing
- Dead Code Removed: YES
- Real Tests Added: YES

**Critical Issues Identified:**

1. **Config Class Mapping (CRITICAL)**
   - Soliplex requires 1:1 mapping between tool_name and config class
   - Single SQLToolConfig with generic tool_name won't be found
   - **Fix**: Create subclasses per tool (ListTablesConfig, QueryConfig, etc.)

2. **Connection Cache Thrashing**
   - Single global `_cached_adapter` variable causes issues
   - Multiple rooms with different DBs will thrash the cache
   - **Fix**: Use `dict[hash, adapter]` for concurrent support

3. **Per-Room Configuration**
   - Env vars prevent room-specific database overrides
   - **Fix**: Support database_url in tools list items

**Changes Made:**
- Created per-tool config subclasses (ListTablesConfig, QueryConfig, etc.)
- Changed cache from single variable to dict
- Added per-room database configuration examples
- Updated registration to list all config classes

### Iteration 3: Final Validation (Gemini gemini-3-pro-preview)

**Validation Checklist:**

| Item | Status |
|------|--------|
| Per-tool config classes defined | PASS |
| Dict-based adapter cache | PASS |
| Registration lists ALL classes | PASS |
| Per-room database_url override | PASS |
| Real SQLite integration tests | PASS |
| Pydantic-AI idioms mentioned | PASS |
| AG-UI StateDeltaEvent documented | PASS |
| Environment variable fallback | FIXED (was FAIL) |

**Final Issue Found:**
- SQLToolConfigBase used hardcoded defaults instead of env var values
- **Fix**: Use `dataclasses.field(default_factory=...)` with `_env_settings`

**Changes Made:**
- Config defaults now use `default_factory` to read from `_env_settings`
- Environment variables properly serve as fallback defaults

**FINAL APPROVAL**: Plan approved for implementation after env var fix applied.

## Files for Review

| File | Purpose |
|------|---------|
| `README.md` | Project documentation |
| `PLAN_SQLTOOLS.md` | Implementation plan |
| `ANALYSIS_SQLTOOLS.md` | This document |
| `docs/architecture.md` | Architecture diagram |

### Reference Files

| File | Purpose |
|------|---------|
| `/Users/runyaga/dev/soliplex/src/soliplex/tools.py` | Soliplex tool patterns |
| `/Users/runyaga/dev/soliplex/src/soliplex/config.py` | Configuration patterns |
| `/Users/runyaga/dev/soliplex/src/soliplex/database.py` | Database patterns |
| `/tmp/sql_toolset_temp/src/sql_toolset_pydantic_ai/sql/toolset.py` | Upstream toolset |
| `/tmp/sql_toolset_temp/src/sql_toolset_pydantic_ai/types.py` | Upstream types |

## Conclusions

After 3 iterations of Gemini review, the implementation plan is **APPROVED** with the following key design decisions:

### Architecture
- **Adapter Pattern**: Wraps upstream sql-toolset-pydantic-ai without forking
- **Direct Backend Calls**: Bypasses FunctionToolset overhead for efficiency
- **Dict-based Caching**: Supports concurrent rooms with different databases

### Soliplex Integration
- **Per-tool Config Classes**: Satisfies 1:1 tool_name mapping requirement
- **Environment Fallback**: Defaults from SOLIPLEX_SQL_* env vars
- **Per-room Override**: database_url can be set per room config
- **AG-UI Events**: StateDeltaEvent emission for task progress

### Testing Strategy
- **Unit Tests**: Mock-based for AG-UI event verification
- **Integration Tests**: Real SQLite database for dialect validation

### Final Dual Review (Gemini gemini-3-pro-preview)

**Overall: APPROVED**

**Strengths:**
- Robust connection caching with dict-based strategy
- AG-UI StateDeltaEvent for real-time progress
- Per-tool config subclasses for Soliplex compliance
- Real SQLite integration tests

**Minor Weaknesses:**
- No explicit shutdown hook for _adapter_cache cleanup
- Multi-DB config lookup could be ambiguous (edge case)

**Implementation Recommendations:**
1. Add `close_all()` shutdown hook for cache cleanup
2. Sanitize error messages to avoid leaking sensitive DB details
3. Pin sql-toolset-pydantic-ai to specific commit

### Next Steps
1. Implement Phase 1 (Foundation & Upstream Integration)
2. Follow gate criteria at each phase
3. Maintain 95%+ test coverage throughout
4. Add shutdown hook for connection cleanup
