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
    question: str
) -> List[str]:

    """Extract table names relevant to the question."""

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

    relevant = set()

    q = question.lower()

    for keyword, table in (
        keyword_to_table.items()
    ):

        if keyword in q:

            relevant.add(
                table
            )

    # If nothing matched, provide the complete schema.
    if not relevant:

        return [
            "customers",
            "orders",
            "products",
            "order_items",
            "categories",
            "addresses",
            "payments",
            "shipments",
            "reviews",
            "refunds"
        ]

    return list(
        relevant
    )


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
            question
        )
    )

    filtered = {}

    q_lower = question.lower()

    for table in relevant_tables:

        if table not in full_schema:

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

        kept_cols = [
            column
            for column in cols
            if column.lower()
            in q_lower
        ]

        # If no individual column names appear
        # in the question, keep all columns.
        if not kept_cols:

            kept_cols = cols

        kept_types = {
            column:
                types[column]
            for column in kept_cols
        }

        filtered[
            table
        ] = {

            "columns":
                kept_cols,

            "types":
                kept_types,

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