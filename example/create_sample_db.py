#!/usr/bin/env python3
"""Create sample database with seed data for soliplex_sql demo.

Usage:
    # SQLite (default)
    python example/create_sample_db.py

    # PostgreSQL
    python example/create_sample_db.py --postgres

    # PostgreSQL with custom connection
    python example/create_sample_db.py --postgres \
        --host localhost --port 5432 \
        --user soliplex --password soliplex --database soliplex_test

This creates tables:
- products: Product catalog
- customers: Customer records
- orders: Order headers
- order_items: Order line items
"""

from __future__ import annotations

import argparse
import random
from abc import ABC
from abc import abstractmethod
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Any


class DatabaseAdapter(ABC):
    """Abstract database adapter for cross-database support."""

    @abstractmethod
    def execute(self, sql: str) -> Any:
        """Execute a single SQL statement."""

    @abstractmethod
    def executemany(self, sql: str, params: list[tuple]) -> None:
        """Execute SQL with multiple parameter sets."""

    @abstractmethod
    def fetchall(self, sql: str) -> list[tuple]:
        """Execute query and fetch all results."""

    @abstractmethod
    def fetchone(self, sql: str) -> tuple | None:
        """Execute query and fetch one result."""

    @abstractmethod
    def commit(self) -> None:
        """Commit transaction."""

    @abstractmethod
    def close(self) -> None:
        """Close connection."""


class SQLiteAdapter(DatabaseAdapter):
    """SQLite database adapter."""

    def __init__(self, db_path: Path) -> None:
        import sqlite3

        self.db_path = db_path
        if db_path.exists():
            db_path.unlink()
        self.conn = sqlite3.connect(db_path)

    def execute(self, sql: str) -> Any:
        return self.conn.executescript(sql)

    def executemany(self, sql: str, params: list[tuple]) -> None:
        self.conn.executemany(sql, params)

    def fetchall(self, sql: str) -> list[tuple]:
        return self.conn.execute(sql).fetchall()

    def fetchone(self, sql: str) -> tuple | None:
        return self.conn.execute(sql).fetchone()

    def commit(self) -> None:
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    @property
    def placeholder(self) -> str:
        return "?"


class PostgreSQLAdapter(DatabaseAdapter):
    """PostgreSQL database adapter."""

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
    ) -> None:
        import psycopg2

        self.conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=database,
        )
        self.cursor = self.conn.cursor()

    def execute(self, sql: str) -> Any:
        for stmt in sql.split(";"):
            stmt = stmt.strip()
            if stmt:
                self.cursor.execute(stmt)
        return self.cursor

    def executemany(self, sql: str, params: list[tuple]) -> None:
        self.cursor.executemany(sql, params)

    def fetchall(self, sql: str) -> list[tuple]:
        self.cursor.execute(sql)
        return self.cursor.fetchall()

    def fetchone(self, sql: str) -> tuple | None:
        self.cursor.execute(sql)
        return self.cursor.fetchone()

    def commit(self) -> None:
        self.conn.commit()

    def close(self) -> None:
        self.cursor.close()
        self.conn.close()

    @property
    def placeholder(self) -> str:
        return "%s"


def get_sqlite_schema() -> str:
    """Return SQLite schema."""
    return """
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
        CREATE INDEX idx_order_items_product ON order_items(product_id)
    """


def get_postgres_schema() -> str:
    """Return PostgreSQL schema."""
    return """
        DROP TABLE IF EXISTS order_items CASCADE;
        DROP TABLE IF EXISTS orders CASCADE;
        DROP TABLE IF EXISTS customers CASCADE;
        DROP TABLE IF EXISTS products CASCADE;

        CREATE TABLE products (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            category VARCHAR(100) NOT NULL,
            price DECIMAL(10, 2) NOT NULL,
            stock_quantity INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE customers (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            city VARCHAR(100),
            country VARCHAR(100) DEFAULT 'USA',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE orders (
            id SERIAL PRIMARY KEY,
            customer_id INTEGER NOT NULL REFERENCES customers(id),
            order_date DATE NOT NULL,
            status VARCHAR(50) DEFAULT 'completed',
            total_amount DECIMAL(10, 2)
        );

        CREATE TABLE order_items (
            id SERIAL PRIMARY KEY,
            order_id INTEGER NOT NULL REFERENCES orders(id),
            product_id INTEGER NOT NULL REFERENCES products(id),
            quantity INTEGER NOT NULL,
            unit_price DECIMAL(10, 2) NOT NULL
        );

        CREATE INDEX idx_orders_date ON orders(order_date);
        CREATE INDEX idx_orders_customer ON orders(customer_id);
        CREATE INDEX idx_order_items_order ON order_items(order_id);
        CREATE INDEX idx_order_items_product ON order_items(product_id)
    """


def seed_products(db: DatabaseAdapter) -> None:
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
    ph = db.placeholder
    sql = f"""
        INSERT INTO products (name, category, price, stock_quantity)
        VALUES ({ph}, {ph}, {ph}, {ph})
    """
    db.executemany(sql, products)


def seed_customers(db: DatabaseAdapter) -> None:
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
    ph = db.placeholder
    sql = f"""
        INSERT INTO customers (name, email, city, country)
        VALUES ({ph}, {ph}, {ph}, {ph})
    """
    db.executemany(sql, customers)


def seed_orders(db: DatabaseAdapter) -> None:
    """Generate orders over the past 90 days."""
    random.seed(42)

    today = datetime.now().date()
    start_date = today - timedelta(days=90)

    product_weights = {
        1: 5, 2: 20, 3: 15, 4: 10, 5: 3,
        6: 12, 7: 8, 8: 10, 9: 2, 10: 1,
        11: 25, 12: 18, 13: 15, 14: 4, 15: 20,
    }

    prices = {row[0]: row[1] for row in db.fetchall("SELECT id, price FROM products")}

    order_id = 0
    orders = []
    order_items = []

    current_date = start_date
    while current_date <= today:
        days_ago = (today - current_date).days
        base_orders = 3 if current_date.weekday() < 5 else 1

        if days_ago < 30:
            base_orders += 2
        elif days_ago < 60:
            base_orders += 1

        num_orders = random.randint(base_orders, base_orders + 3)

        for _ in range(num_orders):
            order_id += 1
            customer_id = random.randint(1, 15)

            item_weights = [40, 35, 20, 5]
            num_items = random.choices([1, 2, 3, 4], weights=item_weights)[0]

            product_ids = list(product_weights.keys())
            wts = list(product_weights.values())
            selected = list(set(random.choices(product_ids, weights=wts, k=num_items)))

            total = 0
            for product_id in selected:
                qty_weights = [70, 25, 5]
                quantity = random.choices([1, 2, 3], weights=qty_weights)[0]
                unit_price = prices[product_id]
                total += quantity * unit_price
                order_items.append((order_id, product_id, quantity, unit_price))

            orders.append((
                order_id, customer_id, current_date.isoformat(),
                "completed", round(total, 2),
            ))

        current_date += timedelta(days=1)

    ph = db.placeholder
    orders_sql = f"""
        INSERT INTO orders (id, customer_id, order_date, status, total_amount)
        VALUES ({ph}, {ph}, {ph}, {ph}, {ph})
    """
    db.executemany(orders_sql, orders)

    items_sql = f"""
        INSERT INTO order_items (order_id, product_id, quantity, unit_price)
        VALUES ({ph}, {ph}, {ph}, {ph})
    """
    db.executemany(items_sql, order_items)

    print(f"Created {len(orders)} orders with {len(order_items)} line items")


def print_summary(db: DatabaseAdapter, is_postgres: bool = False) -> None:
    """Print database summary."""
    print("\n=== Database Summary ===")

    tables = ["products", "customers", "orders", "order_items"]
    for table in tables:
        row = db.fetchone(f"SELECT COUNT(*) FROM {table}")
        print(f"  {table}: {row[0]} records")

    if is_postgres:
        month_sql = """
            SELECT
                COUNT(DISTINCT o.id) as order_count,
                SUM(oi.quantity) as items_sold,
                ROUND(SUM(o.total_amount)::numeric, 2) as revenue
            FROM orders o
            JOIN order_items oi ON o.id = oi.order_id
            WHERE DATE_TRUNC('month', o.order_date) =
                  DATE_TRUNC('month', CURRENT_DATE)
        """
    else:
        month_sql = """
            SELECT
                COUNT(DISTINCT o.id) as order_count,
                SUM(oi.quantity) as items_sold,
                ROUND(SUM(o.total_amount), 2) as revenue
            FROM orders o
            JOIN order_items oi ON o.id = oi.order_id
            WHERE strftime('%Y-%m', o.order_date) = strftime('%Y-%m', 'now')
        """

    row = db.fetchone(month_sql)
    print("\n=== This Month ===")
    print(f"  Orders: {row[0]}")
    print(f"  Items sold: {row[1]}")
    print(f"  Revenue: ${row[2]:,.2f}" if row[2] else "  Revenue: $0.00")


def main() -> None:
    """Create and seed the database."""
    parser = argparse.ArgumentParser(description="Create sample database")
    parser.add_argument(
        "--postgres", action="store_true",
        help="Use PostgreSQL instead of SQLite"
    )
    parser.add_argument("--host", default="localhost", help="PostgreSQL host")
    parser.add_argument("--port", type=int, default=5432, help="PostgreSQL port")
    parser.add_argument("--user", default="soliplex", help="PostgreSQL user")
    parser.add_argument("--password", default="soliplex", help="PostgreSQL password")
    parser.add_argument(
        "--database", default="soliplex_test",
        help="PostgreSQL database name"
    )
    args = parser.parse_args()

    if args.postgres:
        print(f"Creating PostgreSQL database: {args.database}@{args.host}:{args.port}")
        db: DatabaseAdapter = PostgreSQLAdapter(
            host=args.host,
            port=args.port,
            user=args.user,
            password=args.password,
            database=args.database,
        )
        db.execute(get_postgres_schema())
    else:
        db_path = Path(__file__).parent / "sample_data.db"
        print(f"Creating SQLite database: {db_path}")
        db = SQLiteAdapter(db_path)
        db.execute(get_sqlite_schema())

    try:
        seed_products(db)
        seed_customers(db)
        seed_orders(db)
        db.commit()
        print_summary(db, is_postgres=args.postgres)
        print("\nDatabase created successfully!")
    finally:
        db.close()


if __name__ == "__main__":
    main()
