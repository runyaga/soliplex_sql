# soliplex_sql Example Installation

This directory contains a complete working example of the soliplex_sql plugin.

## Quick Start

```bash
# 1. Create the sample database (if not exists)
python example/create_sample_db.py

# 2. Start the server
soliplex-cli serve example/installation.yaml

# 3. Open http://localhost:8000/docs
```

## Rooms

### SQL Assistant (`sql-assistant`)

A general-purpose SQL database assistant for exploring and querying data.

**Capabilities:**
- List and describe database tables
- Execute SQL queries
- Explain query plans
- Sample data exploration

**Example prompts:**
- "What tables are in the database?"
- "Describe the products table"
- "Show me a sample of the orders data"
- "How many records are in each table?"

### Sales Database (`sales-db`)

A specialized room for sales data analysis and business insights.

**Capabilities:**
- Sales trend analysis
- Top products/customers reporting
- Revenue analytics
- Time-based queries

**Example prompts:**
- "Show me this month's top selling products"
- "What's our revenue trend?"
- "Who are our top customers?"
- "Which product categories perform best?"

## Sample Database

The sample database (`sample_data.db`) contains realistic e-commerce data:

### Tables

#### `products` (15 records)
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| name | TEXT | Product name |
| category | TEXT | Category (Electronics, Home Office, Office Supplies, Accessories) |
| price | DECIMAL | Unit price |
| stock_quantity | INTEGER | Current stock |
| created_at | TIMESTAMP | Creation date |

**Sample products:**
- Laptop Pro 15 ($1,299.99)
- Wireless Mouse ($29.99)
- Ergonomic Chair ($299.99)
- Notebook Pack ($12.99)

#### `customers` (15 records)
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| name | TEXT | Customer name |
| email | TEXT | Email (unique) |
| city | TEXT | City |
| country | TEXT | Country (default: USA) |
| created_at | TIMESTAMP | Registration date |

#### `orders` (~450 records)
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| customer_id | INTEGER | FK to customers |
| order_date | DATE | Order date |
| status | TEXT | Status (completed) |
| total_amount | DECIMAL | Order total |

**Data characteristics:**
- 90 days of order history
- More orders on weekdays
- Growth trend (more recent = more orders)

#### `order_items` (~800 records)
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| order_id | INTEGER | FK to orders |
| product_id | INTEGER | FK to products |
| quantity | INTEGER | Quantity ordered |
| unit_price | DECIMAL | Price at time of order |

### Data Patterns

The seed data includes realistic patterns:

1. **Product popularity:** Some products sell more frequently
   - Bestsellers: Notebook Pack, Wireless Mouse, Cable Management Kit
   - Premium items: Laptop Pro, Standing Desk (fewer but higher value)

2. **Time trends:**
   - More orders in recent weeks (growth simulation)
   - Higher volume on weekdays

3. **Order composition:**
   - 1-4 items per order
   - Most orders have 1-2 items

### Regenerating Data

To reset the database with fresh data:

```bash
python example/create_sample_db.py
```

This will:
- Delete existing `sample_data.db`
- Create fresh schema
- Seed with new randomized data (deterministic seed for reproducibility)
- Print summary statistics

## Configuration Files

```
example/
├── installation.yaml      # Main installation config
├── create_sample_db.py    # Database creation script
├── sample_data.db         # SQLite database (generated)
├── EXAMPLE.md             # This file
└── rooms/
    ├── sql-assistant/
    │   └── room_config.yaml
    └── sales-db/
        └── room_config.yaml
```

## Model Configuration

The example rooms use `gpt-oss:20b` for reliable tool calling. Not all Ollama models support OpenAI-compatible tool calling properly. Models with built-in tool templates (like gpt-oss) work best.

**Known compatibility:**
- ✅ `gpt-oss:20b` - Built-in tool template, works reliably
- ⚠️ `qwen3-coder:30b` - May output tool calls as text instead of invoking them
- ❌ `qwen3-coder-tools:30b` - Uses custom (non-OpenAI) tool format

## SQL Tool Configuration

Each room can configure SQL tools with:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `database_url` | SQLite/PostgreSQL connection string | Required |
| `read_only` | Prevent write operations | `true` |
| `max_rows` | Limit query results | `100` |
| `query_timeout` | Query timeout in seconds | `30.0` |

Example:
```yaml
tools:
  - tool_name: soliplex_sql.tools.query
    database_url: "sqlite:///./example/sample_data.db"
    read_only: true
    max_rows: 500
```
