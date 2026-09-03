# this is like manager to the ecommerce file 
# db.py

import sqlite3
from pathlib import Path

# Real populated SQLite database
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database" / "ecommerce.db"


def get_connection():
    """Create and return a connection to the populated SQLite database."""
    return sqlite3.connect(DB_PATH)


def execute_query(query):
    """Execute a SELECT query and return the results."""
    conn = get_connection()

    try:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        return rows
    finally:
        conn.close()