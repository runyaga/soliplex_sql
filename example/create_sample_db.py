#!/usr/bin/env python3
"""Create sample database with seed data for soliplex_sql demo.

Run this script to create/reset the sample database:
    python example/create_sample_db.py

This creates example/sample_data.db with:
- products: Product catalog
- customers: Customer records
- orders: Order headers
- order_items: Order line items

Data is designed to work with room suggestions like:
- "Show me this month's top selling products"
- "What's our revenue trend?"
- "How many records are in each table?"
"""

import random
import sqlite3
from datetime import datetime
from datetime import timedelta
from pathlib import Path

# Database path
DB_PATH = Path(__file__).parent / "sample_data.db"


def create_schema(conn: sqlite3.Connection) -> None:
    """Create database tables."""
    conn.executescript("""
        DROP TABLE IF EXISTS order_items;
        DROP TABLE IF EXISTS orders;
        DROP TABLE IF EXISTS customers;
        DROP TABLE IF EXISTS products;

        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price DECIMAL(10, 2) NOT NULL,
            stock_quantity INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            city TEXT,
            country TEXT DEFAULT 'USA',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            order_date DATE NOT NULL,
            status TEXT DEFAULT 'completed',
            total_amount DECIMAL(10, 2),
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        );

        CREATE TABLE order_items (
            id INTEGER PRIMARY KEY,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price DECIMAL(10, 2) NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        );

        CREATE INDEX idx_orders_date ON orders(order_date);
        CREATE INDEX idx_orders_customer ON orders(customer_id);
        CREATE INDEX idx_order_items_order ON order_items(order_id);
        CREATE INDEX idx_order_items_product ON order_items(product_id);
    """)


def seed_products(conn: sqlite3.Connection) -> None:
    """Insert sample products."""
    products = [
        ("Laptop Pro 15", "Electronics", 1299.99, 50),
        ("Wireless Mouse", "Electronics", 29.99, 200),
        ("USB-C Hub", "Electronics", 49.99, 150),
        ("Mechanical Keyboard", "Electronics", 149.99, 75),
        ("Monitor 27inch", "Electronics", 399.99, 30),
        ("Webcam HD", "Electronics", 79.99, 100),
        ("Headphones Pro", "Electronics", 199.99, 60),
        ("Desk Lamp LED", "Home Office", 34.99, 120),
        ("Ergonomic Chair", "Home Office", 299.99, 25),
        ("Standing Desk", "Home Office", 499.99, 15),
        ("Notebook Pack", "Office Supplies", 12.99, 500),
        ("Pen Set Premium", "Office Supplies", 24.99, 300),
        ("Desk Organizer", "Office Supplies", 19.99, 200),
        ("Whiteboard 4x3", "Office Supplies", 89.99, 40),
        ("Cable Management Kit", "Accessories", 15.99, 250),
    ]
    sql = """
        INSERT INTO products (name, category, price, stock_quantity)
        VALUES (?, ?, ?, ?)
    """
    conn.executemany(sql, products)


def seed_customers(conn: sqlite3.Connection) -> None:
    """Insert sample customers."""
    customers = [
        ("Alice Johnson", "alice@example.com", "New York", "USA"),
        ("Bob Smith", "bob@example.com", "Los Angeles", "USA"),
        ("Carol Williams", "carol@example.com", "Chicago", "USA"),
        ("David Brown", "david@example.com", "Houston", "USA"),
        ("Eva Martinez", "eva@example.com", "Phoenix", "USA"),
        ("Frank Garcia", "frank@example.com", "Philadelphia", "USA"),
        ("Grace Lee", "grace@example.com", "San Antonio", "USA"),
        ("Henry Wilson", "henry@example.com", "San Diego", "USA"),
        ("Ivy Taylor", "ivy@example.com", "Dallas", "USA"),
        ("Jack Anderson", "jack@example.com", "San Jose", "USA"),
        ("Karen Thomas", "karen@example.com", "Austin", "USA"),
        ("Leo Jackson", "leo@example.com", "Jacksonville", "USA"),
        ("Mia White", "mia@example.com", "Fort Worth", "USA"),
        ("Noah Harris", "noah@example.com", "Columbus", "USA"),
        ("Olivia Martin", "olivia@example.com", "Charlotte", "USA"),
    ]
    sql = """
        INSERT INTO customers (name, email, city, country)
        VALUES (?, ?, ?, ?)
    """
    conn.executemany(sql, customers)


def seed_orders(conn: sqlite3.Connection) -> None:
    """Generate orders over the past 90 days with realistic patterns."""
    random.seed(42)  # Reproducible data

    today = datetime.now().date()
    start_date = today - timedelta(days=90)

    # Product popularity weights (some products sell more)
    product_weights = {
        1: 5,   # Laptop Pro - high value, moderate sales
        2: 20,  # Wireless Mouse - bestseller
        3: 15,  # USB-C Hub - popular
        4: 10,  # Mechanical Keyboard
        5: 3,   # Monitor - expensive, fewer sales
        6: 12,  # Webcam
        7: 8,   # Headphones
        8: 10,  # Desk Lamp
        9: 2,   # Ergonomic Chair - expensive
        10: 1,  # Standing Desk - expensive
        11: 25, # Notebook Pack - high volume
        12: 18, # Pen Set
        13: 15, # Desk Organizer
        14: 4,  # Whiteboard
        15: 20, # Cable Kit - popular add-on
    }

    # Get product prices
    cursor = conn.execute("SELECT id, price FROM products")
    prices = {row[0]: row[1] for row in cursor.fetchall()}

    order_id = 0
    orders = []
    order_items = []

    # Generate orders for each day
    current_date = start_date
    while current_date <= today:
        # More orders on weekdays, seasonal bump in recent weeks
        days_ago = (today - current_date).days
        base_orders = 3 if current_date.weekday() < 5 else 1

        # Recent weeks have more orders (growth trend)
        if days_ago < 30:
            base_orders += 2
        elif days_ago < 60:
            base_orders += 1

        num_orders = random.randint(base_orders, base_orders + 3)

        for _ in range(num_orders):
            order_id += 1
            customer_id = random.randint(1, 15)

            # Generate 1-4 items per order
            item_weights = [40, 35, 20, 5]
            num_items = random.choices([1, 2, 3, 4], weights=item_weights)[0]

            # Select products based on weights
            product_ids = list(product_weights.keys())
            wts = list(product_weights.values())
            selected = random.choices(product_ids, weights=wts, k=num_items)
            selected = list(set(selected))  # Remove duplicates

            total = 0
            for product_id in selected:
                qty_weights = [70, 25, 5]
                quantity = random.choices([1, 2, 3], weights=qty_weights)[0]
                unit_price = prices[product_id]
                total += quantity * unit_price
                item = (order_id, product_id, quantity, unit_price)
                order_items.append(item)

            order = (
                order_id, customer_id, current_date.isoformat(),
                "completed", round(total, 2),
            )
            orders.append(order)

        current_date += timedelta(days=1)

    # Insert orders
    orders_sql = """
        INSERT INTO orders (id, customer_id, order_date, status, total_amount)
        VALUES (?, ?, ?, ?, ?)
    """
    conn.executemany(orders_sql, orders)

    # Insert order items
    items_sql = """
        INSERT INTO order_items (order_id, product_id, quantity, unit_price)
        VALUES (?, ?, ?, ?)
    """
    conn.executemany(items_sql, order_items)

    print(f"Created {len(orders)} orders with {len(order_items)} line items")


def print_summary(conn: sqlite3.Connection) -> None:
    """Print database summary."""
    print("\n=== Database Summary ===")

    tables = ["products", "customers", "orders", "order_items"]
    for table in tables:
        cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  {table}: {count} records")

    # This month's stats
    cursor = conn.execute("""
        SELECT
            COUNT(DISTINCT o.id) as order_count,
            SUM(oi.quantity) as items_sold,
            ROUND(SUM(o.total_amount), 2) as revenue
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        WHERE strftime('%Y-%m', o.order_date) = strftime('%Y-%m', 'now')
    """)
    row = cursor.fetchone()
    print("\n=== This Month ===")
    print(f"  Orders: {row[0]}")
    print(f"  Items sold: {row[1]}")
    print(f"  Revenue: ${row[2]:,.2f}")

    # Top products this month
    cursor = conn.execute("""
        SELECT
            p.name,
            SUM(oi.quantity) as qty,
            ROUND(SUM(oi.quantity * oi.unit_price), 2) as revenue
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        JOIN products p ON oi.product_id = p.id
        WHERE strftime('%Y-%m', o.order_date) = strftime('%Y-%m', 'now')
        GROUP BY p.id
        ORDER BY qty DESC
        LIMIT 5
    """)
    print("\n=== Top 5 Products This Month ===")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} units, ${row[2]:,.2f}")


def main() -> None:
    """Create and seed the database."""
    print(f"Creating database at: {DB_PATH}")

    # Remove existing database
    if DB_PATH.exists():
        DB_PATH.unlink()

    # Create and populate
    conn = sqlite3.connect(DB_PATH)
    try:
        create_schema(conn)
        seed_products(conn)
        seed_customers(conn)
        seed_orders(conn)
        conn.commit()
        print_summary(conn)
        print(f"\nDatabase created successfully: {DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
