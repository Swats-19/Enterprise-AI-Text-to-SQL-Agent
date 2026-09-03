# database/postgres_adapter.py

import psycopg2
from psycopg2 import sql
from typing import Dict, List, Any, Optional
from database.adapter import DatabaseAdapter


class PostgreSQLAdapter(DatabaseAdapter):
    """PostgreSQL implementation of the DatabaseAdapter."""
    
    def __init__(self, host: str, port: int, dbname: str, user: str, password: str):
        self.host = host
        self.port = port
        self.dbname = dbname
        self.user = user
        self.password = password
        self._connection = None
    
    def get_connection(self):
        """Return a connection to the PostgreSQL database."""
        if self._connection is None or self._connection.closed:
            self._connection = psycopg2.connect(
                host=self.host,
                port=self.port,
                dbname=self.dbname,
                user=self.user,
                password=self.password
            )
        return self._connection

    # ============================================================
    # FIXED: get_schema is now a method INSIDE the class
    # ============================================================
    def get_schema(self) -> Dict[str, List[Dict[str, Any]]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get all tables in public schema
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        schema = {}
        for table in tables:
            # Get column info
            cursor.execute("""
                SELECT 
                    column_name,
                    data_type,
                    is_nullable,
                    column_default,
                    ordinal_position
                FROM information_schema.columns
                WHERE table_name = %s
                    AND table_schema = 'public'
                ORDER BY ordinal_position
            """, (table,))
            columns = cursor.fetchall()
            
            # Get primary key
            cursor.execute("""
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                WHERE tc.constraint_type = 'PRIMARY KEY'
                    AND tc.table_name = %s
                    AND tc.table_schema = 'public'
            """, (table,))
            pk_result = cursor.fetchone()
            pk_column = pk_result[0] if pk_result else None
            
            # Get foreign keys
            cursor.execute("""
                SELECT
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage ccu
                    ON ccu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                    AND tc.table_name = %s
                    AND tc.table_schema = 'public'
            """, (table,))
            fk_rows = cursor.fetchall()
            
            # Build a map from column name -> (foreign_table, foreign_column)
            fk_map = {}
            for fk in fk_rows:
                col, ref_table, ref_col = fk
                fk_map[col] = {"table": ref_table, "column": ref_col}
            
            # Build column list with FK info
            column_list = []
            for col in columns:
                col_name, data_type, is_nullable, default, pos = col
                column_list.append({
                    "name": col_name,
                    "type": data_type,
                    "nullable": is_nullable == 'YES',
                    "default": default,
                    "pk": (col_name == pk_column),
                    "position": pos,
                    "fk": fk_map.get(col_name)   # <-- NOW INCLUDED
                })
            
            schema[table] = column_list
        
        conn.close()
        return schema
    
    def execute_query(self, sql: str) -> Dict[str, Any]:
        """
        Execute a SELECT query and return results.
        
        Returns: {
            "success": True/False,
            "data": [...],
            "columns": [...],
            "error": None or str
        }
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(sql)
            
            # Get column names
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            
            # Fetch all rows
            rows = cursor.fetchall()
            
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
    
    def test_connection(self) -> bool:
        """Test if the connection works."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            conn.close()
            return True
        except Exception:
            return False