# Soliplex SQL Architecture

Visual diagram of the adapter architecture.

```
┌─────────────────────────────────────────────────────────┐
│                     Soliplex Agent                       │
│  ┌─────────────────────────────────────────────────────┐│
│  │                  Tool Configs                        ││
│  │         (SQLToolConfig per tool instance)            ││
│  └──────────────────────────┬──────────────────────────┘│
└─────────────────────────────┼───────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│                   soliplex_sql Adapter                   │
│  ┌─────────────────────────────────────────────────────┐│
│  │              SQL Tool Functions                      ││
│  │  • Receives tool_config via Soliplex injection      ││
│  │  • Caches adapters per database configuration       ││
│  │  • Enforces read_only mode when configured          ││
│  └──────────────────────────┬──────────────────────────┘│
└─────────────────────────────┼───────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│              sql-toolset-pydantic-ai                     │
│  ┌─────────────┐  ┌────────────┐  ┌──────────────────┐ │
│  │list_tables  │  │   query    │  │  describe_table  │ │
│  └─────────────┘  └────────────┘  └──────────────────┘ │
│  ┌─────────────┐  ┌────────────┐  ┌──────────────────┐ │
│  │ get_schema  │  │explain_query│ │  sample_query    │ │
│  └─────────────┘  └────────────┘  └──────────────────┘ │
└─────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │    Database     │
                    │ (SQLite/PG/MySQL)│
                    └─────────────────┘
```

## Data Flow

1. **Soliplex Agent** receives user query
2. **Tool Config** injected via Soliplex's native `tool_config` pattern
3. **soliplex_sql Adapter** creates/caches database connection
4. **sql-toolset-pydantic-ai** executes database operations
5. Results returned to agent for response generation
