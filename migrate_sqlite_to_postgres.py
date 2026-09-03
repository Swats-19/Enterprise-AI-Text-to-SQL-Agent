# migrate_sqlite_to_postgres.py

import sqlite3
import psycopg2
from psycopg2 import sql
import os
from dotenv import load_dotenv
load_dotenv()


# ============================================================
# CONFIGURATION
# ============================================================
SQLITE_DB = "database/ecommerce.db"

POSTGRES_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "ecommerce",
    "user": "postgres",
    "password": os.getenv("PGPASSWORD")  # Change this to your actual password
}

# ============================================================
# CONNECT
# ============================================================
print("🔌 Connecting...")
sqlite_conn = sqlite3.connect(SQLITE_DB)
sqlite_cursor = sqlite_conn.cursor()

pg_conn = psycopg2.connect(**POSTGRES_CONFIG)
pg_cursor = pg_conn.cursor()
pg_conn.autocommit = False

# ============================================================
# GET TABLES (exclude internal sqlite_* tables)
# ============================================================
sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
tables = [row[0] for row in sqlite_cursor.fetchall()]
print(f"📋 Tables to migrate: {tables}")

# ============================================================
# DROP EXISTING TABLES IN POSTGRES (in reverse order to avoid FK issues)
# ============================================================
print("\n🗑️ Dropping existing tables...")
for table in reversed(tables):
    try:
        pg_cursor.execute(sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(sql.Identifier(table)))
    except Exception as e:
        print(f"   ⚠️ Could not drop {table}: {e}")
pg_conn.commit()

# ============================================================
# CREATE TABLES IN POSTGRES (manual approach per table)
# ============================================================
print("\n📝 Creating tables in PostgreSQL...")

# Manually define CREATE TABLE statements for each table (matching your schema.sql)
# This avoids conversion errors.

create_statements = {
    "categories": """
        CREATE TABLE categories (
            category_id SERIAL PRIMARY KEY,
            category_name TEXT NOT NULL,
            description TEXT
        )
    """,
    "customers": """
        CREATE TABLE customers (
            customer_id SERIAL PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            date_of_birth TEXT,
            gender TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "addresses": """
        CREATE TABLE addresses (
            address_id SERIAL PRIMARY KEY,
            customer_id INTEGER REFERENCES customers(customer_id),
            address_line1 TEXT NOT NULL,
            address_line2 TEXT,
            city TEXT NOT NULL,
            state TEXT NOT NULL,
            country TEXT NOT NULL,
            pincode TEXT,
            is_default INTEGER DEFAULT 1
        )
    """,
    "products": """
        CREATE TABLE products (
            product_id SERIAL PRIMARY KEY,
            category_id INTEGER REFERENCES categories(category_id),
            product_name TEXT NOT NULL,
            brand TEXT,
            description TEXT,
            price REAL NOT NULL,
            stock INTEGER DEFAULT 0,
            rating REAL DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "orders": """
        CREATE TABLE orders (
            order_id SERIAL PRIMARY KEY,
            customer_id INTEGER REFERENCES customers(customer_id),
            order_date TEXT NOT NULL,
            delivery_date TEXT,
            total_amount REAL NOT NULL,
            status TEXT DEFAULT 'Pending'
        )
    """,
    "order_items": """
        CREATE TABLE order_items (
            order_item_id SERIAL PRIMARY KEY,
            order_id INTEGER REFERENCES orders(order_id),
            product_id INTEGER REFERENCES products(product_id),
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL
        )
    """,
    "payments": """
        CREATE TABLE payments (
            payment_id SERIAL PRIMARY KEY,
            order_id INTEGER REFERENCES orders(order_id),
            payment_method TEXT NOT NULL,
            payment_status TEXT DEFAULT 'Pending',
            payment_date TEXT,
            transaction_id TEXT UNIQUE,
            amount REAL NOT NULL
        )
    """,
    "shipments": """
        CREATE TABLE shipments (
            shipment_id SERIAL PRIMARY KEY,
            order_id INTEGER REFERENCES orders(order_id),
            courier TEXT,
            tracking_number TEXT UNIQUE,
            status TEXT DEFAULT 'Pending',
            shipped_date TEXT,
            delivered_date TEXT
        )
    """,
    "reviews": """
        CREATE TABLE reviews (
            review_id SERIAL PRIMARY KEY,
            customer_id INTEGER REFERENCES customers(customer_id),
            product_id INTEGER REFERENCES products(product_id),
            rating INTEGER CHECK (rating BETWEEN 1 AND 5),
            review_text TEXT,
            review_date TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "refunds": """
        CREATE TABLE refunds (
            refund_id SERIAL PRIMARY KEY,
            order_id INTEGER REFERENCES orders(order_id),
            refund_amount REAL NOT NULL,
            reason TEXT,
            status TEXT DEFAULT 'Pending',
            refund_date TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """
}

for table in tables:
    if table in create_statements:
        try:
            pg_cursor.execute(create_statements[table])
            print(f"   ✅ Created: {table}")
        except Exception as e:
            print(f"   ❌ Error creating {table}: {e}")
    else:
        print(f"   ⚠️ No CREATE statement for {table}, skipping")
pg_conn.commit()

# ============================================================
# COPY DATA
# ============================================================
print("\n📊 Copying data...")

for table in tables:
    # Get data from SQLite
    sqlite_cursor.execute(f"SELECT * FROM {table}")
    rows = sqlite_cursor.fetchall()
    
    if not rows:
        print(f"   ⏭️ No data in {table}")
        continue
    
    # Get column names
    sqlite_cursor.execute(f"PRAGMA table_info({table})")
    columns = [col[1] for col in sqlite_cursor.fetchall()]
    
    placeholders = ", ".join(["%s"] * len(columns))
    column_names = ", ".join([f'"{col}"' for col in columns])
    insert_query = f'INSERT INTO "{table}" ({column_names}) VALUES ({placeholders})'
    
    try:
        # Insert in batches
        batch_size = 1000
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i+batch_size]
            pg_cursor.executemany(insert_query, batch)
        pg_conn.commit()
        print(f"   ✅ {table}: {len(rows)} rows")
    except Exception as e:
        print(f"   ❌ Error inserting into {table}: {e}")
        pg_conn.rollback()

# ============================================================
# VERIFY
# ============================================================
print("\n✅ Verification:")
for table in tables:
    pg_cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
    count = pg_cursor.fetchone()[0]
    print(f"   📊 {table}: {count} rows")

# ============================================================
# CLOSE
# ============================================================
sqlite_conn.close()
pg_conn.close()

print("\n" + "=" * 50)
print("✅ Migration completed successfully!")
print("=" * 50)