# Soliplex SQL Adapter - LLM Review Feedback

This document captures LLM review findings for each phase.

---

## Phase 1 Review (2025-01-31)

**Reviewers:** Gemini pro3, Codex (partial - timed out)

### Source Implementation Analysis

#### CRITICAL: Security Issue

| ID | File:Line | Issue | Status |
|----|-----------|-------|--------|
| S1 | `adapter.py:302` | `read_only` mode not enforced - `query()` directly calls `database.execute()` without checking if mutations should be blocked | ✅ |

**Fix Required:**
```python
async def query(self, sql_query: str, ...):
    if self.read_only:
        normalized = sql_query.strip().upper()
        if not normalized.startswith(("SELECT", "EXPLAIN", "PRAGMA", "SHOW")):
            raise SoliplexSqlError("Database is in read-only mode")
    # ... existing execution logic ...
```

---

#### HIGH: Soliplex Integration Issues

| ID | File:Line | Issue | Status |
|----|-----------|-------|--------|
| I1 | `config.py:65` | `SQLToolConfigBase` missing `tool` and `tool_requires` properties required by Soliplex loader | ✅ |
| I2 | `config.py:102+` | All 6 config subclasses return `kind="sql"` - causes dict key collision in `ctx.deps.tool_configs` | ✅ |
| I3 | `tools.py:44` | `_get_config_from_context` only matches `kind=="sql"`, won't work after I2 fix | ✅ |

**Fix for I1:** Add properties to `SQLToolConfigBase`:
```python
@property
def tool(self) -> Any:
    """Load the tool function associated with this config."""
    import importlib
    module_name, func_name = self.tool_name.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, func_name)

@property
def tool_requires(self) -> str:
    """Return 'fastapi_context' as these tools use RunContext."""
    return "fastapi_context"
```

**Fix for I2:** Change each subclass to have unique kind:
```python
@dataclasses.dataclass
class ListTablesConfig(SQLToolConfigBase):
    tool_name: str = "soliplex_sql.tools.list_tables"

    @property
    def kind(self) -> str:
        return "sql_list_tables"
```

**Fix for I3:** Update matching logic:
```python
# In _get_config_from_context
for config in tool_configs.values():
    if hasattr(config, 'kind') and config.kind.startswith("sql"):
        return config
```

---

#### MEDIUM: Code Quality Issues

| ID | File:Line | Issue | Status |
|----|-----------|-------|--------|
| C1 | `tools.py:84` | `hash()` on tuple not stable across processes, use tuple directly as dict key | ✅ |
| C2 | `README.md:92` | Wrong tool name `execute_query` should be `query` | ✅ |

**Fix for C1:**
```python
# Before
config_hash = hash((tool_config.database_url, ...))
if config_hash in _adapter_cache: ...

# After
cache_key = (tool_config.database_url, tool_config.read_only, tool_config.max_rows)
if cache_key in _adapter_cache: ...
```

---

### Test Analysis

**Deferred** - Fix source issues first, then evaluate test coverage.

Preliminary findings:
- Unit tests cover helpers but not exported tool functions
- No tests for error event emission paths
- No tests for read_only enforcement (because it doesn't exist)
- Mocks may be testing implementation details rather than behavior

---

### Summary

| Category | Issues | Fixed |
|----------|--------|-------|
| Critical (Security) | 1 | 1 ✅ |
| High (Integration) | 3 | 3 ✅ |
| Medium (Quality) | 2 | 2 ✅ |
| **Total** | **6** | **6** |

### Verification Review (2025-01-31)

All issues verified as FIXED by Gemini pro3:

| ID | Status | Verification |
|----|--------|--------------|
| S1 | ✅ | `_check_read_only()` method added, called before `execute()` |
| I1 | ✅ | `tool` and `tool_requires` properties added to base class |
| I2 | ✅ | Each subclass has unique `kind` (e.g., `sql_list_tables`) |
| I3 | ✅ | `_get_config_from_context` uses `startswith("sql")` |
| C1 | ✅ | Cache uses tuple key directly, not `hash()` |
| C2 | ✅ | README uses `query` (not `execute_query`) |

**Notes from verification:**
- S1: Basic prefix check is not immune to SQL comment injection, but acceptable for Phase 1
- I3: First matching config is used if multiple SQL tools configured (by design)

---

## Phase 2 Review

*Pending Phase 1 completion*

---

## Phase 3 Review

*Pending Phase 2 completion*

---

## Phase 4 Review

*Pending Phase 3 completion*
