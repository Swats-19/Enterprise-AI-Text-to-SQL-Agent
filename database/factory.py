from urllib.parse import urlparse

from database.adapter import DatabaseAdapter
from database.postgres_adapter import PostgreSQLAdapter
from database.sqlite_adapter import SQLiteAdapter


def create_adapter(connection_url: str) -> DatabaseAdapter:
    """Create the appropriate database adapter from a connection URL."""
    if not connection_url or not connection_url.strip():
        raise ValueError(
            "DATABASE_URL is required. Add a PostgreSQL connection URL to .env."
        )

    connection_url = connection_url.strip()
    parsed = urlparse(connection_url)
    scheme = parsed.scheme.lower()

    if scheme == "sqlite":
        db_path = connection_url.replace("sqlite://", "", 1)
        return SQLiteAdapter(db_path)

    if scheme in {"postgresql", "postgres"}:
        if not parsed.hostname or not parsed.path.lstrip("/"):
            raise ValueError(
                "DATABASE_URL must include a PostgreSQL host and database name."
            )
        return PostgreSQLAdapter(connection_url=connection_url)

    if scheme == "mysql":
        raise NotImplementedError("MySQL support coming soon")

    raise ValueError(f"Unsupported database type: {scheme or 'missing scheme'}")
