# skills/utils.py
import re
from typing import List


def detect_db_type(db_url: str) -> str:
    """Detect database type from connection URL."""
    if "sqlite" in db_url.lower():
        return "sqlite"
    elif "postgresql" in db_url.lower() or "postgres" in db_url.lower():
        return "postgresql"
    elif "mysql" in db_url.lower():
        return "mysql"
    else:
        return "unknown"


def get_relevant_tables(question: str) -> List[str]:
    """Extract table names relevant to the question using keywords."""
    keyword_to_table = {
        "customer": "customers", "customers": "customers", "user": "customers",
        "order": "orders", "orders": "orders", "purchase": "orders",
        "product": "products", "products": "products",
        "item": "order_items", "items": "order_items", "order_item": "order_items",
        "category": "categories", "categories": "categories",
        "address": "addresses", "addresses": "addresses",
        "payment": "payments", "payments": "payments",
        "shipment": "shipments", "shipments": "shipments",
        "review": "reviews", "reviews": "reviews",
        "refund": "refunds", "refunds": "refunds",
    }
    relevant = set()
    q = question.lower()
    for kw, tbl in keyword_to_table.items():
        if kw in q:
            relevant.add(tbl)
    if not relevant:
        return ["customers", "orders", "products", "order_items", "categories",
                "addresses", "payments", "shipments", "reviews", "refunds"]
    return list(relevant)


def filter_schema(full_schema: dict, question: str) -> dict:
    """Filter schema: keep only relevant tables and columns."""
    relevant_tables = get_relevant_tables(question)
    filtered = {}
    q_lower = question.lower()
    for table in relevant_tables:
        if table not in full_schema:
            continue
        info = full_schema[table]
        cols = info["columns"]
        types = info["types"]
        pk = info["pk"]
        fks = info["foreign_keys"]
        kept_cols = [c for c in cols if c.lower() in q_lower]
        if not kept_cols:
            kept_cols = cols
        kept_types = {c: types[c] for c in kept_cols}
        filtered[table] = {
            "columns": kept_cols,
            "types": kept_types,
            "pk": pk,
            "foreign_keys": fks
        }
    if not filtered:
        return full_schema
    return filtered


def clean_sql(raw_sql: str) -> str:
    """Remove markdown code blocks from SQL."""
    cleaned = re.sub(r'```(?:sql)?\n?(.*?)\n?```', r'\1', raw_sql, flags=re.DOTALL)
    return cleaned.strip()