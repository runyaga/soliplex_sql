# Soliplex SQL Adapter - Refactoring Plan

## Executive Summary

This plan outlines refactoring of `soliplex_sql` to reduce complexity and align with Soliplex's native `tool_config` injection pattern. Based on Gemini analysis of 14 files across both codebases.

---

## LLM Review Process

**IMPORTANT**: When running LLM reviews at phase gates, you MUST:

1. **Use `mcp__gemini__read_files`** (NOT `ask_gemini`)
2. **Use model `gemini-3-pro-preview`**
3. **Include `PLAN_REFACTOR.md`** so Gemini sees the phase objectives
4. **Include ALL source files touched in the phase**

---

## Progress Tracking

### Phase 5: Config Simplification ✅
- [x] Remove 6 redundant config classes (ListTablesConfig, etc.)
- [x] Consolidate to single SQLToolConfig class
- [x] Move SQLToolSettings() to lazy loading in from_yaml
- [x] Update __init__.py exports
- [x] Update tests for config changes
- [x] Run ruff and fix all issues
- [x] Verify tests pass
- [x] **LLM Review: Source** - Gemini pro3 `read_files`
- [x] Commit Phase 5 (2c8cfa5)

### Phase 6: Tool Signature Refactor ✅
- [x] Add `tool_config: SQLToolConfig` parameter to all tools
- [x] Remove `_get_config_from_context()` function
- [x] Remove `ctx: RunContext[Any]` parameter from tools
- [x] Replace `threading.Lock` with `asyncio.Lock`
- [x] Simplify `_get_adapter()` to accept config directly
- [x] Update all unit tests
- [x] Update all functional tests
- [x] Run ruff and fix all issues
- [x] Verify tests pass
- [x] **LLM Review: Source** - Gemini pro3 `read_files`
- [x] Commit Phase 6 (48d1718)

### Phase 7: Example & Documentation Update ✅
- [x] Update example/installation.yaml (single config class)
- [x] Update README.md with new patterns
- [x] Verify example works with soliplex server
- [x] **LLM Review: Docs** - Gemini pro3 `read_files`
- [x] Commit Phase 7 (593cbc7)

### Post-Phase Fix: Kind Property Collision ✅
- [x] Remove SQLToolConfig.kind override (caused tool registry collision)
- [x] Inherit kind from ToolConfig base (derives unique ID from tool_name)
- [x] Update tests for unique per-tool kind values
- [x] Commit fix (c92f1da)

---

## Phase 5: Config Simplification

### Objectives
- Remove unnecessary class hierarchy
- Consolidate 6 config classes into one
- Improve testability with lazy env loading

### 5.1 Current State (Problem)

```python
# 6 classes that differ ONLY by tool_name string:
@dataclasses.dataclass
class ListTablesConfig(SQLToolConfigBase):
    tool_name: str = "soliplex_sql.tools.list_tables"

@dataclasses.dataclass
class GetSchemaConfig(SQLToolConfigBase):
    tool_name: str = "soliplex_sql.tools.get_schema"

# ... 4 more identical classes
```

### 5.2 Target State (Solution)

```python
# Single class - tool_name comes from room_config.yaml
@dataclasses.dataclass
class SQLToolConfig(ToolConfig):
    database_url: str = dataclasses.field(
        default_factory=lambda: SQLToolSettings().database_url
    )
    read_only: bool = dataclasses.field(
        default_factory=lambda: SQLToolSettings().read_only
    )
    max_rows: int = dataclasses.field(
        default_factory=lambda: SQLToolSettings().max_rows
    )
    query_timeout: float = dataclasses.field(
        default_factory=lambda: SQLToolSettings().query_timeout
    )

    @property
    def kind(self) -> str:
        return "sql"
```

### 5.3 Gate Criteria - Phase 5

| Criterion | Target | Status |
|-----------|--------|--------|
| Config classes | Single SQLToolConfig | ⏳ |
| Backwards compat | SQLToolConfig alias works | ⏳ |
| Ruff lint | 0 errors | ⏳ |
| Unit tests | Pass | ⏳ |
| Coverage | ≥90% | ⏳ |

**Gate Checklist:**
- [ ] Only one SQLToolConfig class exists
- [ ] `from soliplex_sql import SQLToolConfig` works
- [ ] `ruff check src tests` passes
- [ ] `pytest tests/unit/test_config.py` passes
- [ ] All config-related tests updated

---

## Phase 6: Tool Signature Refactor

### Objectives
- Use Soliplex's native `tool_config` injection
- Remove manual config lookup
- Fix async locking

### 6.1 Current State (Problem)

```python
# tools.py - Manual config extraction, blocking lock
_adapter_cache: dict[int, SoliplexSQLAdapter] = {}
_cache_lock = threading.Lock()  # BLOCKS EVENT LOOP

def _get_config_from_context(ctx: Any) -> SQLToolConfigBase | None:
    # O(n) iteration through ALL configs
    for config in tool_configs.values():
        if isinstance(config, SQLToolConfigBase):
            return config
    return None

async def list_tables(ctx: RunContext[Any]) -> list[str]:
    adapter = _get_adapter(ctx)  # Uses ctx to find config
    return await adapter.list_tables()
```

### 6.2 Target State (Solution)

```python
# tools.py - Direct injection, async lock
_adapter_cache: dict[tuple, SoliplexSQLAdapter] = {}
_adapter_lock = asyncio.Lock()  # ASYNC-SAFE

async def _get_adapter(config: SQLToolConfig) -> SoliplexSQLAdapter:
    key = (config.database_url, config.read_only, config.max_rows)

    if key in _adapter_cache:
        return _adapter_cache[key]

    async with _adapter_lock:
        if key in _adapter_cache:
            return _adapter_cache[key]

        deps = config.create_deps()
        adapter = SoliplexSQLAdapter(deps)
        _adapter_cache[key] = adapter
        return adapter

# tool_config automatically injected by Soliplex!
async def list_tables(tool_config: SQLToolConfig) -> list[str]:
    adapter = await _get_adapter(tool_config)
    return await adapter.list_tables()
```

### 6.3 How Soliplex Injection Works

From `soliplex/config.py:385-403`:
```python
@property
def tool_with_config(self) -> Callable:
    if self.tool_requires == ToolRequires.TOOL_CONFIG:
        # Binds tool_config=self using functools.partial
        tool_w_config = functools.partial(self.tool, tool_config=self)
        # Hides tool_config from pydantic-ai's view
        return tool_w_config
```

**Result:** Each tool gets ITS OWN config instance injected, enabling different databases per tool.

### 6.4 Gate Criteria - Phase 6

| Criterion | Target | Status |
|-----------|--------|--------|
| Tool signatures | Use tool_config param | ⏳ |
| Lock type | asyncio.Lock | ⏳ |
| Config lookup | Removed | ⏳ |
| Ruff lint | 0 errors | ⏳ |
| Unit tests | Pass | ⏳ |
| Functional tests | Pass | ⏳ |

**Gate Checklist:**
- [ ] All 6 tools have `tool_config: SQLToolConfig` parameter
- [ ] `_get_config_from_context` removed
- [ ] `threading.Lock` replaced with `asyncio.Lock`
- [ ] `ruff check src tests` passes
- [ ] `pytest tests/unit tests/functional` passes

---

## Phase 7: Example & Documentation Update

### Objectives
- Update installation.yaml to single config class
- Update README with new patterns
- Verify end-to-end functionality

### 7.1 Installation.yaml Update

**Before:**
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

**After:**
```yaml
meta:
  tool_configs:
    - soliplex_sql.config.SQLToolConfig
```

### 7.2 Gate Criteria - Phase 7

| Criterion | Target | Status |
|-----------|--------|--------|
| installation.yaml | Single config | ⏳ |
| README | Updated | ⏳ |
| E2E test | Server starts, tools work | ⏳ |

---

## Files to Modify

| File | Phase | Changes |
|------|-------|---------|
| `src/soliplex_sql/config.py` | 5 | Remove 6 classes, consolidate |
| `src/soliplex_sql/__init__.py` | 5 | Update exports |
| `tests/unit/test_config.py` | 5 | Update for single class |
| `src/soliplex_sql/tools.py` | 6 | New signatures, asyncio.Lock |
| `tests/unit/test_tools.py` | 6 | Update tool invocations |
| `tests/functional/*.py` | 6 | Update tool invocations |
| `example/installation.yaml` | 7 | Single config class |
| `README.md` | 7 | Update documentation |

---

## Design Decisions

- **No backwards compatibility aliases** - Clean break, remove all 6 config classes completely

## Risk Assessment

| Change | Risk | Mitigation |
|--------|------|------------|
| Remove 6 config classes | Low | Clean break decided |
| Change tool signatures | Medium | Update all tests first |
| asyncio.Lock | Low | Standard async pattern |
| Remove ctx parameter | Low | Soliplex native pattern |

---

## Verification Plan

### Per-Phase Gate (run after each phase)

- [ ] **Lint**: `ruff check src tests`
- [ ] **Tests**: `pytest tests/unit tests/functional -v`
- [ ] **Build**: `python -m build`
- [ ] **LLM Review**: See instructions below

#### LLM Review Instructions

At the end of each phase, call `mcp__gemini__read_files` to verify the implementation.

**CRITICAL: All file paths MUST be absolute paths** (e.g., `/Users/runyaga/dev/soliplex_sql/src/...`)

**file_paths array must include:**
1. `PLAN_REFACTOR.md` - so Gemini sees the phase objectives
2. All source files modified or created during the phase
3. All test files updated for the phase

**Parameters:**
- `model`: `gemini-3-pro-preview`
- `prompt`: "Review these files against the current phase objectives in PLAN_REFACTOR.md. Verify the implementation matches the target state. Report any issues, missing items, or deviations from the plan."

**Do NOT skip this step.** The review catches issues before committing.

### Final Verification

- [ ] Start soliplex server: `soliplex-cli serve example/installation.yaml`
- [ ] Test SQL tools via AGUI endpoint
