import tempfile
import unittest
from pathlib import Path

from database.adapter import validate_read_only_query
from database.factory import create_adapter


class ReadOnlyQueryTests(unittest.TestCase):
    def test_accepts_select_and_select_cte(self):
        self.assertEqual(validate_read_only_query("SELECT 1"), "SELECT 1")
        self.assertEqual(
            validate_read_only_query("WITH values_cte AS (SELECT 1) SELECT * FROM values_cte"),
            "WITH values_cte AS (SELECT 1) SELECT * FROM values_cte",
        )

    def test_rejects_mutation_and_multiple_statements(self):
        for query in (
            "DELETE FROM customers",
            "SELECT 1; DROP TABLE customers",
            "",
        ):
            with self.subTest(query=query):
                with self.assertRaises(ValueError):
                    validate_read_only_query(query)

    def test_sqlite_adapter_enforces_read_only_queries(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.db"
            adapter = create_adapter(f"sqlite://{database_path}")
            connection = adapter.get_connection()
            connection.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
            connection.execute("INSERT INTO sample (id) VALUES (1)")
            connection.commit()
            connection.close()

            result = adapter.execute_query("SELECT id FROM sample")
            self.assertTrue(result["success"])
            self.assertEqual(result["data"], [(1,)])

            result = adapter.execute_query("DELETE FROM sample")
            self.assertFalse(result["success"])
            self.assertIn("Only one read-only SELECT", result["error"])


class AdapterFactoryTests(unittest.TestCase):
    def test_requires_database_url(self):
        with self.assertRaisesRegex(ValueError, "DATABASE_URL is required"):
            create_adapter("")

    def test_preserves_postgres_connection_url(self):
        connection_url = "postgresql://user:p%40ss@localhost:5433/ecommerce?sslmode=require"
        adapter = create_adapter(connection_url)
        self.assertEqual(adapter.connection_url, connection_url)


if __name__ == "__main__":
    unittest.main()
