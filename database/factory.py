# database/factory.py
from urllib.parse import urlparse
from database.sqlite_adapter import SQLiteAdapter
from database.postgres_adapter import PostgreSQLAdapter
from database.adapter import DatabaseAdapter

def create_adapter(connection_url: str) -> DatabaseAdapter:
    """Create the appropriate database adapter from a connection URL."""
    
    if "sqlite" in connection_url:
        db_path = connection_url.replace("sqlite://", "")
        return SQLiteAdapter(db_path)
    
    elif "postgresql" in connection_url:
        parsed = urlparse(connection_url)
        return PostgreSQLAdapter(
            host=parsed.hostname,
            port=parsed.port or 5432,
            dbname=parsed.path.lstrip("/"),
            user=parsed.username,
            password=parsed.password
        )
    
    elif "mysql" in connection_url:
        # For future MySQL support
        raise NotImplementedError("MySQL support coming soon")
    
    else:
        raise ValueError(f"Unsupported database type: {connection_url}")