# skills/agentic.py

import os
import sys

# ============================================================
# PATH SETUP
# ============================================================

parent_dir = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

sys.path.append(parent_dir)


# ============================================================
# IMPORTS
# ============================================================

from skills.utils import detect_db_type
from skills.orchestrator import run_agent


# ============================================================
# DATABASE URL
# ============================================================

# Put your actual database URL in .env as:
#
# DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5433/ecommerce
#
# This keeps the password out of the source code.

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:YOUR_PASSWORD@localhost:5433/ecommerce"
)


# ============================================================
# TEST BLOCK
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("🧪 TESTING FULL LANGGRAPH AGENT")
    print("=" * 60)


    # ========================================================
    # TEST 1: DATABASE TYPE DETECTION
    # ========================================================

    print("\n" + "=" * 60)
    print("[TEST 1] DATABASE TYPE DETECTION")
    print("=" * 60)

    test_urls = [
        "sqlite://ecommerce.db",
        "postgresql://postgres:password@localhost:5433/ecommerce",
        "mysql://user:pass@localhost:3306/ecommerce"
    ]

    for url in test_urls:

        db_type = detect_db_type(url)

        print(
            f"   URL: {url} → {db_type}"
        )


    # ========================================================
    # TEST 2: DEMO MODE
    # ========================================================
    #
    # Purpose:
    #
    # Force Node 2 to generate deliberately wrong SQL.
    #
    # Expected LangGraph behavior:
    #
    # Node 2
    #   ↓
    # Wrong SQL
    #   ↓
    # Node 3 Judge
    #   ↓
    # Reject
    #   ↓
    # Conditional Edge
    #   ↓
    # Node 2 AGAIN
    #   ↓
    # Corrected SQL
    #
    # skip_human=True is ONLY for this automated test.
    #
    # It prevents the test from stopping at Node 4
    # waiting for console input.
    #
    # It does NOT remove Human-in-the-Loop from the
    # actual Streamlit application.
    # ========================================================

    print("\n" + "=" * 60)
    print("🎬 TEST 2: DEMO MODE")
    print("   Deliberately wrong SQL → Judge rejection")
    print("   → LangGraph retry → regenerated SQL")
    print("=" * 60)

    try:

        result = run_agent(
            question=(
                "Show me the top 5 customers "
                "with the highest total spend"
            ),
            db_url=DB_URL,
            demo_mode=True,
            skip_human=True
        )

        print("\n📊 DEMO MODE RESULTS")
        print("-" * 60)

        print(
            f"Status: "
            f"{result.get('status')}"
        )

        print(
            f"SQL:\n"
            f"{result.get('sql', 'No SQL generated')}"
        )

        print(
            f"\nJudge Approved: "
            f"{result.get('judge_approved')}"
        )

        print(
            f"Judge Feedback: "
            f"{result.get('judge_feedback', 'N/A')}"
        )

        print(
            f"Human Approved: "
            f"{result.get('human_approved')}"
        )

        print(
            f"Execution Error: "
            f"{result.get('execution_error')}"
        )


        # ----------------------------------------------------
        # METRICS
        # ----------------------------------------------------

        metrics = result.get(
            "metrics",
            {}
        )

        attempts = result.get(
            "attempts",
            {}
        )

        print("\n📈 METRICS")
        print("-" * 60)

        print(
            f"Generator Tokens: "
            f"{metrics.get('generator_input_tokens', 0)} "
            f"input + "
            f"{metrics.get('generator_output_tokens', 0)} "
            f"output"
        )

        print(
            f"Judge Tokens: "
            f"{metrics.get('judge_input_tokens', 0)} "
            f"input + "
            f"{metrics.get('judge_output_tokens', 0)} "
            f"output"
        )

        print(
            f"Generator Latency: "
            f"{metrics.get('generator_latency', 0):.2f}s"
        )

        print(
            f"Judge Latency: "
            f"{metrics.get('judge_latency', 0):.2f}s"
        )

        print(
            f"Execution Time: "
            f"{metrics.get('execution_time', 0):.3f}s"
        )

        print(
            f"Total Time: "
            f"{metrics.get('total_time', 0):.2f}s"
        )

        print("\n🔄 ATTEMPTS")
        print("-" * 60)

        print(
            f"Judge: "
            f"{attempts.get('judge', 0)}"
        )

        print(
            f"Human: "
            f"{attempts.get('human', 0)}"
        )

        print(
            f"Execution: "
            f"{attempts.get('execution', 0)}"
        )

    except Exception as e:

        print(
            f"\n❌ DEMO TEST FAILED: {e}"
        )


    # ========================================================
    # TEST 3: NORMAL MODE
    # ========================================================
    #
    # Purpose:
    #
    # Verify the normal path when the LLM generates
    # a correct SQL query.
    #
    # Expected:
    #
    # Node 1.1
    #   ↓
    # Node 1.2
    #   ↓
    # Node 2
    #   ↓
    # Node 3
    #   ↓
    # approved
    #   ↓
    # Node 4
    #   ↓
    # auto-approved because skip_human=True
    #   ↓
    # Node 5
    #   ↓
    # Node 6
    #   ↓
    # END
    #
    # Again, this is ONLY an automated development test.
    # ========================================================

    print("\n" + "=" * 60)
    print("🧪 TEST 3: NORMAL MODE")
    print("   Normal SQL generation → Judge → Execution")
    print("=" * 60)

    try:

        result = run_agent(
            question=(
                "Show me the top 5 customers "
                "with the highest total spend"
            ),
            db_url=DB_URL,
            demo_mode=False,
            skip_human=True
        )

        print("\n📊 NORMAL MODE RESULTS")
        print("-" * 60)

        print(
            f"Status: "
            f"{result.get('status')}"
        )

        print(
            f"SQL:\n"
            f"{result.get('sql', 'No SQL generated')}"
        )

        print(
            f"\nJudge Approved: "
            f"{result.get('judge_approved')}"
        )

        print(
            f"Judge Feedback: "
            f"{result.get('judge_feedback', 'N/A')}"
        )

        print(
            f"Human Approved: "
            f"{result.get('human_approved')}"
        )

        print(
            f"Execution Error: "
            f"{result.get('execution_error')}"
        )


        # ----------------------------------------------------
        # METRICS
        # ----------------------------------------------------

        metrics = result.get(
            "metrics",
            {}
        )

        attempts = result.get(
            "attempts",
            {}
        )

        print("\n📈 METRICS")
        print("-" * 60)

        print(
            f"Generator Tokens: "
            f"{metrics.get('generator_input_tokens', 0)} "
            f"input + "
            f"{metrics.get('generator_output_tokens', 0)} "
            f"output"
        )

        print(
            f"Judge Tokens: "
            f"{metrics.get('judge_input_tokens', 0)} "
            f"input + "
            f"{metrics.get('judge_output_tokens', 0)} "
            f"output"
        )

        print(
            f"Generator Latency: "
            f"{metrics.get('generator_latency', 0):.2f}s"
        )

        print(
            f"Judge Latency: "
            f"{metrics.get('judge_latency', 0):.2f}s"
        )

        print(
            f"Execution Time: "
            f"{metrics.get('execution_time', 0):.3f}s"
        )

        print(
            f"Total Time: "
            f"{metrics.get('total_time', 0):.2f}s"
        )

        print("\n🔄 ATTEMPTS")
        print("-" * 60)

        print(
            f"Judge: "
            f"{attempts.get('judge', 0)}"
        )

        print(
            f"Human: "
            f"{attempts.get('human', 0)}"
        )

        print(
            f"Execution: "
            f"{attempts.get('execution', 0)}"
        )

    except Exception as e:

        print(
            f"\n❌ NORMAL TEST FAILED: {e}"
        )


    # ========================================================
    # COMPLETE
    # ========================================================

    print("\n" + "=" * 60)
    print("✅ TEST RUN COMPLETE")
    print("=" * 60)