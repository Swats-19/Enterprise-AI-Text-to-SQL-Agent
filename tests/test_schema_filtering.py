import unittest

from skills.utils import filter_schema, get_relevant_tables


SCHEMA = {
    "customers": {
        "columns": ["customer_id", "customer_name"],
        "types": {"customer_id": "integer", "customer_name": "text"},
        "pk": "customer_id",
        "foreign_keys": {},
    },
    "assets": {
        "columns": ["asset_id", "customer_id", "asset_name"],
        "types": {
            "asset_id": "integer",
            "customer_id": "integer",
            "asset_name": "text",
        },
        "pk": "asset_id",
        "foreign_keys": {
            "customer_id": {"table": "customers", "column": "customer_id"}
        },
    },
    "support_engineers": {
        "columns": ["engineer_id", "engineer_name"],
        "types": {"engineer_id": "integer", "engineer_name": "text"},
        "pk": "engineer_id",
        "foreign_keys": {},
    },
}


class SchemaFilteringTests(unittest.TestCase):
    def test_matches_tables_discovered_from_live_schema(self):
        tables = get_relevant_tables(
            "Show customer assets",
            list(SCHEMA),
        )
        self.assertEqual(tables, ["assets", "customers"])

    def test_includes_related_tables_and_complete_columns(self):
        filtered = filter_schema(SCHEMA, "List customer assets")
        self.assertEqual(set(filtered), {"assets", "customers"})
        self.assertEqual(filtered["assets"]["columns"], SCHEMA["assets"]["columns"])

    def test_unknown_business_language_keeps_complete_schema(self):
        filtered = filter_schema(SCHEMA, "Show operational activity")
        self.assertEqual(filtered, SCHEMA)


if __name__ == "__main__":
    unittest.main()
