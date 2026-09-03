# skills/nodes.py

import json
import re
import time
import sqlparse

from llm import llm
from skills.state import AgentState


# ============================================================
# NODE 3: LLM-AS-A-JUDGE
# ============================================================

def sql_judge(state: AgentState) -> dict:

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
    # LIGHTWEIGHT JUDGE AFTER HUMAN FEEDBACK
    # ========================================================

    if human_feedback:

        judge_prompt = f"""
You are a senior SQL expert.

The human has already reviewed the previous SQL and provided
feedback. The SQL has now been regenerated based on that feedback.

Human Feedback:
{human_feedback}

Regenerated SQL:
{sql}

Check ONLY:

1. Safety:
   - SELECT queries only.
   - No DROP, DELETE, UPDATE, INSERT, ALTER, CREATE,
     TRUNCATE, or destructive operations.

2. Syntax:
   - Valid PostgreSQL/SQLite SQL.

Do NOT judge semantic correctness.
The human already reviewed that.

Return ONLY valid JSON.

{{"approved": true, "feedback": "Safe and syntactically valid."}}

OR

{{"approved": false, "feedback": "Explain the safety or syntax problem."}}
"""

    # ========================================================
    # FULL JUDGE
    # ========================================================

    else:

        judge_prompt = f"""
You are a senior SQL expert.

Review this SQL query for the user's question.

User Question:
{question}

Generated SQL:
{sql}

Check:

1. Safety
   - SELECT only.
   - No DROP, DELETE, UPDATE, INSERT, ALTER, CREATE,
     TRUNCATE, or other destructive operations.

2. Correctness
   - Does it correctly answer the question?
   - Are tables, columns, joins, filters, grouping,
     ordering, calculations correct?

3. Optimization
   - Is it reasonably efficient?
   - Is LIMIT appropriate?
   - Are unnecessary joins avoided?

4. Syntax
   - Is it valid PostgreSQL/SQLite SQL?

Approve ONLY if safe, syntactically valid,
and correct.

Return ONLY valid JSON.
No markdown.
No explanation outside JSON.

{{"approved": true, "feedback": "Safe, valid, and correct."}}

OR

{{"approved": false, "feedback": "Explain exactly what needs to be fixed."}}
"""

    # ========================================================
    # CALL LLM
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
    # PARSE RESPONSE
    # ========================================================

    approved = False

    feedback = (
        "Judge response could not be parsed. "
        "Please regenerate SQL."
    )

    try:

        clean = str(
            raw
        ).strip()

        # ----------------------------------------------------
        # Remove markdown code fences
        # ----------------------------------------------------

        clean = re.sub(
            r"^```(?:json)?\s*",
            "",
            clean,
            flags=re.IGNORECASE
        )

        clean = re.sub(
            r"\s*```$",
            "",
            clean
        )

        clean = clean.strip()

        # ----------------------------------------------------
        # Direct JSON
        # ----------------------------------------------------

        try:

            judge_result = json.loads(
                clean
            )

        except json.JSONDecodeError:

            # ------------------------------------------------
            # Extract JSON object
            # ------------------------------------------------

            match = re.search(
                r"\{.*\}",
                clean,
                flags=re.DOTALL
            )

            if not match:

                raise

            judge_result = json.loads(
                match.group(0)
            )

        # ----------------------------------------------------
        # Read approval
        # ----------------------------------------------------

        approved = judge_result.get(
            "approved",
            False
        )

        feedback = judge_result.get(
            "feedback",
            "No feedback provided."
        )

        # ----------------------------------------------------
        # Normalize string booleans
        # ----------------------------------------------------

        if isinstance(
            approved,
            str
        ):

            value = approved.lower().strip()

            if value == "true":

                approved = True

            elif value == "false":

                approved = False

            else:

                approved = False

                feedback = (
                    "Judge returned an invalid "
                    "approval value."
                )

        elif not isinstance(
            approved,
            bool
        ):

            approved = False

            feedback = (
                "Judge returned an invalid "
                "approval value."
            )

    except Exception as e:

        print(
            f"[Node 3] ⚠️ Judge parsing failed: {e}"
        )

        print(
            f"[Node 3] Raw judge response: "
            f"{repr(raw)}"
        )

        approved = False

        feedback = (
            "Judge response could not be parsed. "
            "Please regenerate SQL."
        )

    # ========================================================
    # RESULT
    # ========================================================

    print(
        f"[Node 3] Judge approved: "
        f"{approved}"
    )

    if not approved:

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

        "metrics": {

            "judge_input_tokens":
                usage.get(
                    "input_tokens",
                    0
                ),

            "judge_output_tokens":
                usage.get(
                    "output_tokens",
                    0
                ),

            "judge_latency":
                result.get(
                    "latency",
                    0
                )
        }
    }


# ============================================================
# NODE 4: HUMAN APPROVAL
# ============================================================

def human_approval(
    state: AgentState
) -> dict:

    sql = state.get(
        "sql",
        ""
    )

    try:

        formatted_sql = sqlparse.format(
            sql,
            reindent=True,
            keyword_case="upper"
        )

    except Exception:

        formatted_sql = sql

    print("\n" + "=" * 60)
    print("👤 HUMAN APPROVAL REQUIRED")
    print("=" * 60)

    print(
        f"\n📝 SQL to execute:\n"
        f"{formatted_sql}"
    )

    print("\nOptions:")
    print(
        "  [y/yes] → Approve and execute"
    )
    print(
        "  [anything else] → Reject + feedback"
    )

    print("=" * 60)

    user_input = input(
        "👉 Your response: "
    ).strip()

    if user_input.lower() in [
        "y",
        "yes"
    ]:

        print(
            "✅ Human approved. "
            "Proceeding to execution."
        )

        return {

            "human_approved":
                True,

            "human_feedback":
                None,

            "status":
                "approved"
        }

    feedback = user_input

    if not feedback:

        feedback = (
            "SQL rejected by human. "
            "Please review and regenerate."
        )

    print(
        "🔄 Human rejected SQL."
    )

    print(
        f"📝 Feedback: {feedback}"
    )

    return {

        "human_approved":
            False,

        "human_feedback":
            feedback,

        "status":
            "feedback"
    }


# ============================================================
# NODE 5: QUERY EXECUTION
# ============================================================

def sql_executor(
    state: AgentState
) -> dict:

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
            f"[Node 5] ❌ Execution exception: "
            f"{e}"
        )

        return {

            "data":
                None,

            "columns":
                None,

            "execution_error":
                str(e),

            "status":
                "error",

            "metrics": {

                "execution_time":
                    execution_time
            }
        }

    execution_time = (
        time.time() - start
    )

    if result["success"]:

        print(
            f"[Node 5] ✅ Query executed successfully. "
            f"Rows: {len(result['data'])} "
            f"(Time: {execution_time:.3f}s)"
        )

        return {

            "data":
                result["data"],

            "columns":
                result["columns"],

            "execution_error":
                None,

            "status":
                "success",

            "metrics": {

                "execution_time":
                    execution_time
            }
        }

    print(
        f"[Node 5] ❌ Query execution failed: "
        f"{result['error']}"
    )

    return {

        "data":
            None,

        "columns":
            None,

        "execution_error":
            result["error"],

        "status":
            "error",

        "metrics": {

            "execution_time":
                execution_time
        }
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

    if not data:

        summary = (
            "No data returned."
        )

    else:

        num_rows = len(data)

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
                    for k, v
                    in list(
                        sample_dict.items()
                    )[:3]
                ]
            )

            summary += (
                f"Sample: {sample_str}"
                f"{'...' if num_cols > 3 else ''}"
            )

    print(
        "[Node 6] ✅ Summary generated."
    )

    return {

        "summary":
            summary,

        "status":
            "success"
    }