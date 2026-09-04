# skills/utils.py

import re

from typing import List


# ============================================================
# DATABASE TYPE DETECTION
# ============================================================

def detect_db_type(
    db_url: str
) -> str:

    """Detect database type from connection URL."""

    if "sqlite" in db_url.lower():

        return "sqlite"

    elif (
        "postgresql" in db_url.lower()
        or
        "postgres" in db_url.lower()
    ):

        return "postgresql"

    elif "mysql" in db_url.lower():

        return "mysql"

    else:

        return "unknown"


# ============================================================
# RELEVANT TABLE DETECTION
# ============================================================

def get_relevant_tables(
    question: str,
    available_tables: List[str]
) -> List[str]:

    """Match a question against tables discovered from the live database."""

    keyword_to_table = {

        "customer":
            "customers",

        "customers":
            "customers",

        "user":
            "customers",

        "order":
            "orders",

        "orders":
            "orders",

        "purchase":
            "orders",

        "product":
            "products",

        "products":
            "products",

        "item":
            "order_items",

        "items":
            "order_items",

        "order_item":
            "order_items",

        "category":
            "categories",

        "categories":
            "categories",

        "address":
            "addresses",

        "addresses":
            "addresses",

        "payment":
            "payments",

        "payments":
            "payments",

        "shipment":
            "shipments",

        "shipments":
            "shipments",

        "review":
            "reviews",

        "reviews":
            "reviews",

        "refund":
            "refunds",

        "refunds":
            "refunds"
    }

    table_lookup = {
        table.lower(): table
        for table in available_tables
    }
    question_text = question.lower()
    question_tokens = set(re.findall(r"[a-z0-9_]+", question_text))
    relevant = set()

    for table in available_tables:
        normalized = table.lower()
        spaced = normalized.replace("_", " ")
        variants = {
            normalized,
            spaced,
            normalized.removesuffix("s"),
            spaced.removesuffix("s"),
        }
        if any(
            variant in question_tokens
            or (len(variant) > 2 and variant in question_text)
            for variant in variants
        ):
            relevant.add(table)

    for keyword, table in keyword_to_table.items():
        actual_table = table_lookup.get(table)
        if actual_table and keyword in question_tokens:
            relevant.add(actual_table)

    return sorted(relevant) if relevant else list(available_tables)


# ============================================================
# SCHEMA FILTERING
# ============================================================

def filter_schema(
    full_schema: dict,
    question: str
) -> dict:

    """Filter schema to relevant tables and columns."""

    relevant_tables = (
        get_relevant_tables(
            question,
            list(full_schema)
        )
    )

    related_tables = set(relevant_tables)
    for table in relevant_tables:
        for reference in full_schema[table].get("foreign_keys", {}).values():
            referenced_table = reference.get("table")
            if referenced_table in full_schema:
                related_tables.add(referenced_table)

    for table, info in full_schema.items():
        references = info.get("foreign_keys", {}).values()
        if any(reference.get("table") in related_tables for reference in references):
            related_tables.add(table)

    filtered = {}

    for table in full_schema:

        if table not in related_tables:

            continue

        info = full_schema[
            table
        ]

        cols = info[
            "columns"
        ]

        types = info[
            "types"
        ]

        pk = info[
            "pk"
        ]

        fks = info[
            "foreign_keys"
        ]

        filtered[
            table
        ] = {

            "columns":
                cols,

            "types":
                types,

            "pk":
                pk,

            "foreign_keys":
                fks
        }

    if not filtered:

        return full_schema

    return filtered


# ============================================================
# SQL CLEANING
# ============================================================

def clean_sql(
    raw_sql: str
) -> str:

    """Remove markdown code fences from SQL."""

    if not raw_sql:

        return ""

    cleaned = raw_sql.strip()

    # Remove ```sql ... ```
    cleaned = re.sub(
        r"^```(?:sql)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned
    )

    return cleaned.strip()