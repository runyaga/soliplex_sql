# soliplex_sql - Future Improvements

Based on Gemini's review of the integration test suite.

## Test Suite Enhancements

### 1. Data Seeding Strategy
**Priority:** Medium

Currently tests run against `sqlite:///:memory:` which means `list_tables` returns empty results and `describe_table` relies on graceful error handling.

**Improvement:** Create a Pytest fixture that:
- Creates a temporary SQLite file seeded with 1-2 tables (`users`, `orders`)
- Updates `SOLIPLEX_SQL_DATABASE_URL` env var
- Allows `test_describe_table_tool` to assert on actual schema values

```python
@pytest.fixture
def seeded_database(tmp_path):
    db_path = tmp_path / "test.db"
    # Create tables with sample data
    # Set SOLIPLEX_SQL_DATABASE_URL
    yield db_path
    # Cleanup
```

### 2. Strict Payload Assertion
**Priority:** Low

Current tests check `len(tool_results) > 0` but don't validate the actual values.

**Improvement:** Parse JSON inside `TOOL_CALL_END` events and assert:
- `SELECT 1 + 1` returns exactly `2`
- Catches serialization bugs where query runs but result format is malformed

### 3. Authentication Testing
**Priority:** Low (when OIDC enabled)

Currently OIDC is disabled in `installation.yaml` for demo purposes.

**Improvement:** When production uses OIDC:
- Add test case with `oidc_paths` enabled
- Verify plugin doesn't bypass authz when SQL tools are accessed
- Test unauthorized access returns 401/403

## Current Test Coverage

| Category | Tests | Status |
|----------|-------|--------|
| Smoke Tests | 18 | Passing |
| Functional Tests | 7 | Passing |
| **Total** | **25** | **All passing** |

## Validated Pipeline

- Server startup and configuration loading
- Room configuration (sql-assistant, sales-db)
- Tool binding (list_tables, query, describe_table, etc.)
- AGUI endpoints and thread management
- Agent → Tool → Database execution via SSE events
- Error handling (graceful failures)

## Completed Refactor (Reference)

Refactored to single `SQLToolConfig` with native Soliplex `tool_config` injection:
- Phase 5 - Config consolidation: 2c8cfa5
- Phase 6 - Tool signatures: 48d1718
- Phase 7 - Docs update: 593cbc7
- Kind property fix: c92f1da
