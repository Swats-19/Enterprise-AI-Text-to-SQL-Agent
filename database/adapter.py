# database/adapter.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any

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