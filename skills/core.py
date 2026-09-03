
import os
import sys
import re
import time

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

from database.factory import create_adapter
from llm import llm
from skills.state import AgentState
from skills.utils import detect_db_type, clean_sql


# ============================================================
# NODE 1.1: DETECT + CONNECT
# ============================================================

def detect_and_connect(db_url: str) -> dict:
    """Node 1.1: Detect DB type AND create the adapter."""
    db_type = detect_db_type(db_url)
    adapter = create_adapter(db_url)
    if hasattr(adapter, 'test_connection'):
        if not adapter.test_connection():
            raise ConnectionError(f"Failed to connect to {db_url}")
    print(f"[Node 1.1] Connected to {db_type}: {db_url}")
    return {"db_type": db_type, "adapter": adapter}


# ============================================================
# NODE 1.2: READ SCHEMA FROM ADAPTER
# ============================================================

def read_schema_from_adapter(adapter) -> dict:
    """Node 1.2: Read full metadata using the stored adapter."""
    raw_schema = adapter.get_schema()
    schema = {}
    for table_name, columns in raw_schema.items():
        column_names = []
        column_types = {}
        pk = None
        foreign_keys = {}
        for col in columns:
            col_name = col.get("name")
            col_type = col.get("type")
            is_pk = col.get("pk", False)
            column_names.append(col_name)
            column_types[col_name] = col_type
            if is_pk:
                pk = col_name
            fk_info = col.get("fk")
            if fk_info:
                foreign_keys[col_name] = {"table": fk_info["table"], "column": fk_info["column"]}
        schema[table_name] = {
            "columns": column_names,
            "types": column_types,
            "pk": pk,
            "foreign_keys": foreign_keys
        }
    return schema


# ============================================================
# NODE 2: SQL GENERATOR (UPDATED)
# ============================================================

def sql_generator(state: AgentState) -> dict:
    """Node 2: Generate SQL using the filtered schema."""
    question = state["question"]
    schema = state.get("filtered_schema", {})
    db_type = state.get("db_type", "unknown")
    previous_feedback = state.get("feedback", "")
    attempt = state.get("attempts", 0)
    demo_mode = state.get("demo_mode", False)

    # DEMO MODE: Force wrong SQL on first attempt
    if demo_mode and attempt == 0:
        print("\n" + "=" * 60)
        print("🎬 [DEMO MODE] Intentionally generating WRONG SQL on first attempt...")
        print("=" * 60)
        wrong_sql = """
SELECT * FROM orders WHERE total_amount > 100;
"""
        print("[DEMO] ❌ Generated WRONG SQL (missing customer info):")
        print(wrong_sql)
        return {
            "sql": wrong_sql,
            "attempts": 1,
            "status": "pending",
            "metrics": {
                "generator_input_tokens": 0,
                "generator_output_tokens": 0,
                "generator_latency": 0
            }
        }

    # Build schema description
    schema_text = ""
    for table_name, info in schema.items():
        schema_text += f"Table: {table_name}\n"
        schema_text += f"  Primary Key: {info['pk']}\n"
        schema_text += f"  Columns: {', '.join(info['columns'])}\n"
        if info.get('foreign_keys'):
            fk_parts = []
            for col, ref in info['foreign_keys'].items():
                fk_parts.append(f"{col} → {ref['table']}.{ref['column']}")
            schema_text += f"  Foreign Keys: {', '.join(fk_parts)}\n"
        schema_text += "\n"

    # Build prompt
    prompt = f"""
You are a SQL expert. Generate a SQL SELECT query for the user's question.

Database Type: {db_type}

Question: {question}

Database Schema (only relevant tables and columns):
{schema_text}

Rules:
- Only SELECT queries allowed.
- Use proper JOINs and WHERE clauses as needed.
- Add a LIMIT 100 to avoid huge results.
- Use SQL syntax compatible with {db_type}.
- Return ONLY the SQL query, no explanation, no markdown.
"""

    if previous_feedback:
        prompt += f"""
        
IMPORTANT: Your previous attempt was rejected with this feedback:
{previous_feedback}

Please fix the issues and generate a corrected SQL query.
"""

    # Call the generator-specific LLM method
    result = llm.invoke_generator(prompt)
    raw_sql = result["content"]
    usage = result["usage"]

    cleaned_sql = clean_sql(raw_sql)

    attempts = state.get("attempts", 0) + 1
    print(f"[Node 2] Generated SQL (attempt {attempts}) | Tokens: {usage.get('input_tokens', 0)}+{usage.get('output_tokens', 0)} | Latency: {usage.get('total_time', 0):.2f}s")
    if previous_feedback:
        print(f"[Node 2] Using feedback from previous attempt to correct SQL.")

    return {
        "sql": cleaned_sql,
        "attempts": attempts,
        "status": "pending",
        "metrics": {
            "generator_input_tokens": usage.get("input_tokens", 0),
            "generator_output_tokens": usage.get("output_tokens", 0),
            "generator_latency": usage.get("total_time", 0)
        }
    }