# skills/nodes.py

import json
import re
import time

from llm import llm
from skills.state import AgentState
from skills.utils import clean_sql


# ============================================================
# HELPER: ACCUMULATE METRICS
# ============================================================

def accumulate_metric(
    existing_metrics: dict,
    key: str,
    value
) -> dict:

    metrics = dict(
        existing_metrics or {}
    )

    metrics[key] = (
        metrics.get(key, 0)
        + (value or 0)
    )

    return metrics


# ============================================================
# NODE 1.1: DETECT + CONNECT
# ============================================================

def detect_and_connect(
    db_url: str
) -> dict:

    from skills.utils import detect_db_type
    from database.factory import create_adapter

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
        "db_type": db_type,
        "adapter": adapter
    }


# ============================================================
# NODE 1.2: READ SCHEMA FROM ADAPTER
# ============================================================

def read_schema_from_adapter(
    adapter
) -> dict:

    raw_schema = adapter.get_schema()

    schema = {}

    for table_name, columns in raw_schema.items():

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


# ============================================================
# NODE 2: SQL GENERATOR
# ============================================================

def sql_generator(
    state: AgentState
) -> dict:

    question = state[
        "question"
    ]

    schema = state.get(
        "filtered_schema",
        {}
    )

    db_type = state.get(
        "db_type",
        "unknown"
    )

    # --------------------------------------------------------
    # HUMAN FEEDBACK
    # --------------------------------------------------------

    human_feedback = state.get(
        "human_feedback",
        ""
    )

    previous_feedback = state.get(
        "feedback",
        ""
    )

    attempt = state.get(
        "attempts",
        0
    )

    demo_mode = state.get(
        "demo_mode",
        False
    )

    # ========================================================
    # DEMO MODE
    # ========================================================

    if (
        demo_mode
        and
        attempt == 0
    ):

        print(
            "\n"
            + "=" * 60
        )

        print(
            "[DEMO MODE] "
            "Intentionally generating WRONG SQL "
            "on first attempt..."
        )

        print(
            "=" * 60
        )

        wrong_sql = """
SELECT * FROM orders
WHERE total_amount > 100;
"""

        print(
            "[DEMO] Generated intentionally incorrect SQL "
            "(missing customer information):"
        )

        print(
            wrong_sql
        )

        existing_metrics = state.get(
            "metrics",
            {}
        )

        return {

            "sql":
                wrong_sql,

            "attempts":
                1,

            "status":
                "pending",

            "metrics": {
                **existing_metrics,

                "generator_input_tokens":
                    existing_metrics.get(
                        "generator_input_tokens",
                        0
                    ),

                "generator_output_tokens":
                    existing_metrics.get(
                        "generator_output_tokens",
                        0
                    ),

                "generator_latency":
                    existing_metrics.get(
                        "generator_latency",
                        0
                    )
            }
        }

    # ========================================================
    # BUILD SCHEMA DESCRIPTION
    # ========================================================

    schema_text = ""

    for table_name, info in schema.items():

        schema_text += (
            f"Table: {table_name}\n"
        )

        schema_text += (
            f"  Primary Key: "
            f"{info['pk']}\n"
        )

        schema_text += (
            f"  Columns: "
            f"{', '.join(info['columns'])}\n"
        )

        if info.get(
            "foreign_keys"
        ):

            fk_parts = []

            for col, ref in info[
                "foreign_keys"
            ].items():

                fk_parts.append(
                    f"{col} → "
                    f"{ref['table']}."
                    f"{ref['column']}"
                )

            schema_text += (
                f"  Foreign Keys: "
                f"{', '.join(fk_parts)}\n"
            )

        schema_text += "\n"

    # ========================================================
    # BUILD BASE PROMPT
    # ========================================================

    prompt = f"""
You are a SQL expert.

Generate a SQL SELECT query for the user's question.

Database Type:
{db_type}

Original User Question:
{question}

Database Schema:
{schema_text}

Rules:
- Only SELECT queries are allowed.
- Use proper JOINs and WHERE clauses as needed.
- Use SQL syntax compatible with {db_type}.
- Use LIMIT 100 as a safety cap only when the user has not
  specified a different LIMIT.
- If the user or human reviewer specifies a LIMIT, use that
  exact LIMIT instead of LIMIT 100.
- Return ONLY the SQL query.
- Do not return explanations.
- Do not return markdown.
"""

    # ========================================================
    # HUMAN CORRECTION HAS HIGHEST PRIORITY
    # ========================================================

    if human_feedback:

        prompt += f"""

IMPORTANT — HUMAN UPDATED REQUIREMENT

The human reviewer has explicitly changed the requirement.

Human's updated requirement:
{human_feedback}

This human requirement MUST take precedence over the
original user question wherever they conflict.

For example:

Original question:
"Show me the top 5 customers."

Human correction:
"Change the limit to limit 2."

Correct result:
LIMIT 2

Do NOT change LIMIT 2 back to LIMIT 5.

Apply the human's requested change exactly.

If the human requested a change involving:
- LIMIT
- WHERE
- ORDER BY
- selected columns
- filtering
- aggregation
- JOIN
- sorting

make that exact change.

Do NOT simply regenerate the previous SQL unchanged.

Return ONLY the corrected SQL query.
"""

    # ========================================================
    # JUDGE / EXECUTION FEEDBACK
    # ========================================================

    elif previous_feedback:

        prompt += f"""

IMPORTANT — CORRECTION REQUIRED

The previous SQL attempt was rejected or failed.

Feedback:
{previous_feedback}

Fix the issue described in the feedback.

Return ONLY the corrected SQL query.
"""

    # ========================================================
    # CALL GENERATOR LLM
    # ========================================================

    result = llm.invoke_generator(
        prompt
    )

    raw_sql = result.get(
        "content",
        ""
    )

    usage = result.get(
        "usage",
        {}
    )

    cleaned_sql = clean_sql(
        raw_sql
    )

    # ========================================================
    # ATTEMPT COUNT
    # ========================================================

    attempts = (
        state.get(
            "attempts",
            0
        )
        + 1
    )

    # ========================================================
    # METRICS
    # ========================================================

    input_tokens = usage.get(
        "input_tokens",
        0
    )

    output_tokens = usage.get(
        "output_tokens",
        0
    )

    latency = result.get(
        "latency",
        usage.get(
            "total_time",
            0
        )
    )

    existing_metrics = state.get(
        "metrics",
        {}
    )

    metrics = {
        **existing_metrics,

        "generator_input_tokens":
            existing_metrics.get(
                "generator_input_tokens",
                0
            )
            + input_tokens,

        "generator_output_tokens":
            existing_metrics.get(
                "generator_output_tokens",
                0
            )
            + output_tokens,

        "generator_latency":
            existing_metrics.get(
                "generator_latency",
                0
            )
            + latency
    }

    # ========================================================
    # LOGGING
    # ========================================================

    print(
        f"[Node 2] Generated SQL "
        f"(attempt {attempts}) | "
        f"Tokens: "
        f"{input_tokens}+{output_tokens} | "
        f"Latency: {latency:.2f}s"
    )

    if human_feedback:

        print(
            "[Node 2] Using HUMAN feedback "
            "as updated requirement:"
        )

        print(
            f"[Node 2] {human_feedback}"
        )

    elif previous_feedback:

        print(
            "[Node 2] Using feedback from "
            "previous attempt to correct SQL."
        )

    print(
        f"[Node 2] SQL:\n{cleaned_sql}"
    )

    return {

        "sql":
            cleaned_sql,

        "attempts":
            attempts,

        "status":
            "pending",

        "metrics":
            metrics
    }


# ============================================================
# NODE 3: SQL JUDGE
# ============================================================

def sql_judge(
    state: AgentState
) -> dict:

    sql = state.get(
        "sql",
        ""
    )

    question = state.get(
        "question",
        ""
    )

    human_feedback = state.get(
        "human_feedback",
        ""
    )

    # ========================================================
    # HUMAN-FEEDBACK-AWARE JUDGE
    # ========================================================

    if human_feedback:

        judge_prompt = f"""
You are a SQL safety and correctness judge.

Original user question:
{question}

Human correction / updated requirement:
{human_feedback}

Generated SQL:
{sql}

============================================================
IMPORTANT PRIORITY RULE
============================================================

The human correction is an explicit update to the user's
requirement.

When the human correction conflicts with the original
question, the human correction MUST take precedence.

For example:

Original user question:
"Show me the top 5 customers with the highest total spend."

Human correction:
"Change the limit to limit 2."

Generated SQL:
SELECT ...
LIMIT 2;

The SQL MUST be considered correct with respect to the
UPDATED requirement.

Do NOT reject the SQL merely because it differs from the
original question when that difference was explicitly
requested by the human.

============================================================
EVALUATION
============================================================

Evaluate the generated SQL for:

1. Safety
2. Valid SQL syntax
3. Correct tables and columns
4. Correct JOINs
5. Correct aggregation
6. Correct filtering
7. Correct ordering
8. Compatibility with the database
9. Compliance with the original request where it does NOT
   conflict with the human correction
10. Compliance with the human correction

The human correction has higher priority than the original
question.

If the human says LIMIT 2 and the SQL uses LIMIT 2,
do NOT reject it because the original question said LIMIT 5.

Return ONLY valid JSON.

Approved example:

{{
    "approved": true,
    "feedback": "The SQL satisfies the updated human requirement."
}}

Rejected example:

{{
    "approved": false,
    "feedback": "The SQL does not satisfy the human's updated requirement."
}}
"""

    # ========================================================
    # NORMAL JUDGE
    # ========================================================

    else:

        judge_prompt = f"""
You are an expert SQL safety and correctness judge.

User question:
{question}

Generated SQL:
{sql}

Evaluate the SQL for:

1. Safety
2. Correctness
3. Relevance to the question
4. SQL syntax
5. Correct tables and columns
6. Appropriate joins
7. Correct aggregation
8. Correct filtering
9. Correct ordering
10. Reasonable optimization

Only SELECT queries are allowed.

Return ONLY valid JSON.

Approved:

{{
    "approved": true,
    "feedback": "short explanation"
}}

Rejected:

{{
    "approved": false,
    "feedback": "what needs to be fixed"
}}
"""

    # ========================================================
    # CALL JUDGE LLM
    # ========================================================

    result = llm.invoke_judge(
        judge_prompt
    )

    raw = result.get(
        "content",
        ""
    )

    usage = result.get(
        "usage",
        {}
    )

    # ========================================================
    # PARSE JSON
    # ========================================================

    approved = False
    feedback = ""

    try:

        cleaned = raw.strip()

        cleaned = re.sub(
            r"^```json\s*",
            "",
            cleaned,
            flags=re.IGNORECASE
        )

        cleaned = re.sub(
            r"^```\s*",
            "",
            cleaned
        )

        cleaned = re.sub(
            r"\s*```$",
            "",
            cleaned
        )

        parsed = json.loads(
            cleaned
        )

        approved = bool(
            parsed.get(
                "approved",
                False
            )
        )

        feedback = parsed.get(
            "feedback",
            ""
        )

    except Exception as e:

        print(
            "[Node 3] WARNING: "
            "Failed to parse judge response:",
            e
        )

        approved = False

        feedback = (
            "Judge returned an invalid "
            "response format."
        )

    # ========================================================
    # METRICS
    # ========================================================

    input_tokens = usage.get(
        "input_tokens",
        0
    )

    output_tokens = usage.get(
        "output_tokens",
        0
    )

    latency = result.get(
        "latency",
        0
    )

    existing_metrics = state.get(
        "metrics",
        {}
    )

    metrics = {
        **existing_metrics,

        "judge_input_tokens":
            existing_metrics.get(
                "judge_input_tokens",
                0
            )
            + input_tokens,

        "judge_output_tokens":
            existing_metrics.get(
                "judge_output_tokens",
                0
            )
            + output_tokens,

        "judge_latency":
            existing_metrics.get(
                "judge_latency",
                0
            )
            + latency
    }

    # ========================================================
    # LOGGING
    # ========================================================

    print(
        f"[Node 3] "
        f"{'APPROVED' if approved else 'REJECTED'} | "
        f"Tokens: "
        f"{input_tokens}+{output_tokens} | "
        f"Latency: {latency:.2f}s"
    )

    if feedback:

        print(
            f"[Node 3] Feedback: "
            f"{feedback}"
        )

    return {

        "judge_approved":
            approved,

        "judge_feedback":
            feedback,

        "status":
            "pending",

        "metrics":
            metrics
    }


# ============================================================
# NODE 5: SQL EXECUTOR
# ============================================================

def sql_executor(
    state: AgentState
) -> dict:

    MAX_RESULT_ROWS = 100

    sql = state.get(
        "sql"
    )

    adapter = state.get(
        "adapter"
    )

    if not adapter:

        return {

            "data":
                None,

            "columns":
                None,

            "row_count":
                0,

            "execution_error":
                "No database adapter found.",

            "status":
                "error"
        }

    start = time.time()

    try:

        result = adapter.execute_query(
            sql
        )

    except Exception as e:

        execution_time = (
            time.time() - start
        )

        print(
            f"[Node 5] ERROR: "
            f"Execution exception: {e}"
        )

        existing_metrics = state.get(
            "metrics",
            {}
        )

        metrics = {
            **existing_metrics,

            "execution_time":
                execution_time
        }

        return {

            "data":
                None,

            "columns":
                None,

            "row_count":
                0,

            "execution_error":
                str(e),

            "status":
                "error",

            "metrics":
                metrics
        }

    execution_time = (
        time.time() - start
    )

    # ========================================================
    # SUCCESS
    # ========================================================

    if result["success"]:

        full_data = result["data"]

        preview_data = full_data[
            :MAX_RESULT_ROWS
        ]

        actual_row_count = len(
            full_data
        )

        print(
            f"[Node 5] "
            f"Query executed successfully. "
            f"Rows: {actual_row_count} "
            f"(Time: {execution_time:.3f}s)"
        )

        if (
            actual_row_count
            > MAX_RESULT_ROWS
        ):

            print(
                f"[Node 5] Keeping first "
                f"{MAX_RESULT_ROWS} rows in state "
                f"to keep LangGraph/LangSmith "
                f"traces lightweight."
            )

        existing_metrics = state.get(
            "metrics",
            {}
        )

        metrics = {
            **existing_metrics,

            "execution_time":
                execution_time
        }

        return {

            "data":
                preview_data,

            "columns":
                result["columns"],

            "row_count":
                actual_row_count,

            "execution_error":
                None,

            "status":
                "success",

            "metrics":
                metrics
        }

    # ========================================================
    # EXECUTION ERROR
    # ========================================================

    print(
        f"[Node 5] ERROR: "
        f"Query execution failed: "
        f"{result['error']}"
    )

    existing_metrics = state.get(
        "metrics",
        {}
    )

    metrics = {
        **existing_metrics,

        "execution_time":
            execution_time
    }

    return {

        "data":
            None,

        "columns":
            None,

        "row_count":
            0,

        "execution_error":
            result["error"],

        "status":
            "error",

        "metrics":
            metrics
    }


# ============================================================
# NODE 6: RESULT EXPLAINER
# ============================================================

def result_explainer(
    state: AgentState
) -> dict:

    data = state.get(
        "data"
    )

    columns = state.get(
        "columns"
    )

    num_rows = state.get(
        "row_count",
        len(data) if data else 0
    )

    if not data:

        summary = (
            "No data returned."
        )

    else:

        num_cols = (
            len(columns)
            if columns
            else 0
        )

        summary = (
            f"✅ Query returned "
            f"**{num_rows}** rows and "
            f"**{num_cols}** columns.\n"
        )

        if (
            num_rows > 0
            and num_cols > 0
        ):

            sample = data[0]

            sample_dict = dict(
                zip(
                    columns,
                    sample
                )
            )

            sample_str = ", ".join(
                [
                    f"{k}: {v}"
                    for k, v in list(
                        sample_dict.items()
                    )[:3]
                ]
            )

            summary += (
                f"Sample: {sample_str}"
                f"{'...' if num_cols > 3 else ''}"
            )

        if (
            num_rows
            > len(data)
        ):

            summary += (
                f"\nShowing the first "
                f"{len(data)} rows "
                f"as a preview."
            )

    print(
        "[Node 6] "
        "Summary generated."
    )

    return {

        "summary":
            summary,

        "status":
            "success"
    }