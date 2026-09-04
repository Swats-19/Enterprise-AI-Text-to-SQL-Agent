# database/adapter.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any
import sqlparse


def validate_read_only_query(query: str) -> str:
    """Return a normalized query after verifying it is one SELECT statement."""
    if not query or not query.strip():
        raise ValueError("SQL query cannot be empty.")

    statements = [statement for statement in sqlparse.parse(query) if str(statement).strip()]
    if len(statements) != 1 or statements[0].get_type() != "SELECT":
        raise ValueError("Only one read-only SELECT query is allowed.")

    return query.strip()

class DatabaseAdapter(ABC):
    """Abstract class for database operations."""
    
    @abstractmethod
    def get_connection(self):
        """Return a database connection."""
        pass
    
    @abstractmethod
    def get_schema(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get database schema: tables, columns, types, relationships.
        Returns: {
            "table_name": [
                {"name": "col1", "type": "INTEGER", "nullable": False, "pk": True},
                ...
            ]
        }
        """
        pass
    
    @abstractmethod
    def execute_query(self, sql: str) -> Dict[str, Any]:
        """
        Execute a SELECT query.
        Returns: {
            "success": True/False,
            "data": [...],
            "columns": [...],
            "error": None or str
        }
        """
        pass