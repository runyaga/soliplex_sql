# Soliplex SQL Architecture

Visual diagram of the adapter architecture.

```
┌─────────────────────────────────────────────────────────┐
│                     Soliplex Agent                       │
│  ┌─────────────────────────────────────────────────────┐│
│  │                Agent Dependencies                    ││
│  │  ┌─────────────┐  ┌────────────┐  ┌──────────────┐ ││
│  │  │ agui_emitter│  │tool_configs│  │   state      │ ││
│  │  └─────────────┘  └────────────┘  └──────────────┘ ││
│  └──────────────────────────┬──────────────────────────┘│
└─────────────────────────────┼───────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│                   soliplex_sql Adapter                   │
│  ┌─────────────────────────────────────────────────────┐│
│  │              SQL Tool Wrappers                       ││
│  │  • Injects AgentDependencies context                ││
│  │  • Emits StateDeltaEvents for task progress         ││
│  │  • Maps to Soliplex ToolConfig system               ││
│  └──────────────────────────┬──────────────────────────┘│
└─────────────────────────────┼───────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│              sql-toolset-pydantic-ai                     │
│  ┌─────────────┐  ┌────────────┐  ┌──────────────────┐ │
│  │list_tables  │  │execute_sql │  │schema_discovery  │ │
│  └─────────────┘  └────────────┘  └──────────────────┘ │
│  ┌─────────────┐  ┌────────────┐  ┌──────────────────┐ │
│  │insert_row   │  │update_rows │  │delete_rows       │ │
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
2. **Agent Dependencies** provide context (emitter, config, state)
3. **soliplex_sql Adapter** wraps calls with AG-UI events
4. **sql-toolset-pydantic-ai** executes database operations
5. Results flow back through the stack with progress updates
