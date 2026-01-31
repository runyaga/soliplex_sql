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

## Phase 2 Review (2025-01-31)

**Reviewer:** Gemini pro3

### Source Implementation Analysis

| ID | File:Line | Issue | Severity | Status |
|----|-----------|-------|----------|--------|
| H1 | `adapter.py:20` | CTE queries (`WITH...`) blocked by read-only check | HIGH | ✅ |
| H2 | `tools.py:50-53` | First SQL config returned in multi-DB setup | HIGH | N/A (by design) |
| H3 | `tools.py:90-96` | Race condition in adapter caching | HIGH | ✅ |
| M4 | `adapter.py:304` | SQL comment prefix causes false rejection | MEDIUM | Deferred |
| M5 | `adapter.py:40` | `datetime.UTC` requires Python 3.11+ | MEDIUM | N/A (requires 3.12+) |
| M6 | `tools.py:28` | Module-level cache has no auto-cleanup | MEDIUM | Documented |

### Analysis Notes

**H1 (CTE Support):**
- Current `_READONLY_PREFIXES` missing `"WITH"` for CTEs
- Fix: Add `"WITH"` to the tuple

**H2 (Config Resolution):**
- This is by design (documented in Phase 1 review)
- Each room should configure ONE database
- Multi-DB support would require passing specific config to tool

**H3 (Race Condition):**
- Concurrent requests could create duplicate adapters
- Fix: Use `asyncio.Lock` or accept duplicate creation (cache is dict)
- Note: dict assignment is atomic in CPython, but duplicate creation wastes resources

**M5 (Python Version):**
- Project requires Python 3.12+ per pyproject.toml
- `datetime.UTC` is valid for target versions

**M6 (Connection Lifecycle):**
- `close_all()` is provided for cleanup
- Should be called on application shutdown
- Documentation covers this

### Test Analysis

| ID | Location | Issue | Severity | Status |
|----|----------|-------|----------|--------|
| T1 | `test_adapter.py:83-113` | AG-UI tests will need removal in Phase 2.5 | HIGH | Tracked for 2.5 |
| T2 | `unit/conftest.py:20-36` | AG-UI fixtures for removal in Phase 2.5 | HIGH | Tracked for 2.5 |
| T3 | `test_tools.py:37-54` | `_get_agui_emitter` tests obsolete in 2.5 | HIGH | Tracked for 2.5 |
| T4 | `test_tool_wrappers.py:80` | Manual cache injection tests implementation | MEDIUM | Acceptable |
| T5 | `test_real_database.py` | Missing invalid SQL edge case test | MEDIUM | Deferred |
| T6 | `test_adapter.py` | Over-mocking database behavior | LOW | Acceptable |
| T7 | `test_real_database.py` | Missing empty query test | LOW | Deferred |

**Notes:**
- T1-T3: AG-UI related tests tracked for Phase 2.5 cleanup
- T4: Direct cache manipulation is pragmatic for testing caching
- T5-T7: Low priority edge cases, can be added in Phase 4

---

## Phase 2.5 Review (2025-01-31)

**Reviewer:** Gemini pro3

### Scope: AG-UI Event Emission Removal

All AG-UI related code successfully removed:
- `_create_task_status_patch()` removed from adapter.py
- `_emit_task_progress()` removed from adapter.py
- `agui_emitter` and `related_task_id` parameters removed from all methods
- `_get_agui_emitter()` removed from tools.py
- `TestGetAGUIEmitter` class removed from test_tools.py
- `TestCreateTaskStatusPatch` class removed from test_adapter.py
- `mock_agui_emitter` fixtures removed from conftest.py files

### Source Implementation Analysis

| ID | File:Line | Issue | Severity | Status |
|----|-----------|-------|----------|--------|
| T1 | `tools.py:202` | Thread Safety: `close_all()` iterates cache without lock | MEDIUM | ✅ |
| S2 | `adapter.py:139` | Security: Prefix check vulnerable to multi-statement SQL | HIGH | Deferred |
| P3 | `adapter.py:169` | Performance: All rows fetched before truncation | MEDIUM | Documented |

### Analysis Notes

**T1 (Thread Safety):**
- `close_all()` was iterating `_adapter_cache.values()` without lock
- If `_get_adapter` runs concurrently, could cause `RuntimeError` or orphaned connections
- **Fixed:** Now acquires lock, copies adapters, clears cache, then closes outside lock

**S2 (Multi-Statement SQL):**
- `_check_read_only` uses prefix matching which doesn't catch `SELECT 1; DROP TABLE`
- SQLite by default doesn't execute multiple statements in single call
- Documented limitation, acceptable for current use case
- Could be hardened in Phase 4 if needed

**P3 (Memory Usage):**
- `query()` fetches all rows then slices to `max_rows`
- Could OOM on massive result sets
- This is an upstream library limitation
- Documented as expected behavior

### Test Coverage

All Phase 2 tracked items (T1-T3) completed:
- T1: AG-UI tests removed from test_adapter.py ✅
- T2: AG-UI fixtures removed from conftest.py ✅
- T3: `_get_agui_emitter` tests removed from test_tools.py ✅

**Coverage:** 90.51% (exceeds 80% requirement)

### Summary

| Category | Issues | Fixed |
|----------|--------|-------|
| Medium (Thread Safety) | 1 | 1 ✅ |
| High (Security) | 1 | Deferred |
| Medium (Performance) | 1 | Documented |

---

## Phase 3 Review

*Pending Phase 2.5 completion*

---

## Phase 4 Review

*Pending Phase 3 completion*
