# database/sqlite_adapter.py
import sqlite3
from typing import Dict, List, Any
from database.adapter import DatabaseAdapter

class SQLiteAdapter(DatabaseAdapter):
    def __init__(self, db_path: str = "ecommerce.db"):
        self.db_path = db_path
    
    def get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def get_schema(self) -> Dict[str, List[Dict[str, Any]]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        schema = {}
        for table in tables:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            schema[table] = [
                {
                    "name": col[1],
                    "type": col[2],
                    "nullable": col[3] == 0,
                    "pk": col[5] == 1
                }
                for col in columns
            ]
        
        conn.close()
        return schema
    
    def execute_query(self, sql: str) -> Dict[str, Any]:
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            conn.close()
            return {
                "success": True,
                "data": rows,
                "columns": columns,
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "data": [],
                "columns": [],
                "error": str(e)
            }