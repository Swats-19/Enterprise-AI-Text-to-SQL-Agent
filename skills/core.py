# skills/core.py

import os
import sys

# ============================================================
# PATH SETUP
# ============================================================

parent_dir = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

if parent_dir not in sys.path:

    sys.path.append(
        parent_dir
    )


# ============================================================
# IMPORTS
# ============================================================

from database.factory import create_adapter
from skills.utils import detect_db_type


# ============================================================
# NODE 1.1: DETECT + CONNECT
# ============================================================

def detect_and_connect(
    db_url: str
) -> dict:

    """
    Detect database type and create the adapter.

    The live adapter is returned to the caller but should
    NOT be stored in LangGraph checkpoint state.
    """

    db_type = detect_db_type(
        db_url
    )

    adapter = create_adapter(
        db_url
    )

    if hasattr(
        adapter,
        "test_connection"
    ):

        if not adapter.test_connection():

            raise ConnectionError(
                "Failed to connect to database."
            )

    print(
        f"[Node 1.1] Connected to "
        f"{db_type}"
    )

    return {
        "db_type":
            db_type,

        "adapter":
            adapter
    }


# ============================================================
# NODE 1.2: READ SCHEMA
# ============================================================

def read_schema_from_adapter(
    adapter
) -> dict:

    """
    Read full database metadata from the adapter.
    """

    raw_schema = (
        adapter.get_schema()
    )

    schema = {}

    for table_name, columns in (
        raw_schema.items()
    ):

        column_names = []
        column_types = {}
        pk = None
        foreign_keys = {}

        for col in columns:

            col_name = col.get(
                "name"
            )

            col_type = col.get(
                "type"
            )

            is_pk = col.get(
                "pk",
                False
            )

            column_names.append(
                col_name
            )

            column_types[
                col_name
            ] = col_type

            if is_pk:

                pk = col_name

            fk_info = col.get(
                "fk"
            )

            if fk_info:

                foreign_keys[
                    col_name
                ] = {

                    "table":
                        fk_info["table"],

                    "column":
                        fk_info["column"]
                }

        schema[
            table_name
        ] = {

            "columns":
                column_names,

            "types":
                column_types,

            "pk":
                pk,

            "foreign_keys":
                foreign_keys
        }

    return schema