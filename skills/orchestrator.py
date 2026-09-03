
# skills/orchestrator.py

from langgraph.graph import StateGraph, START, END

from skills.state import AgentState
from skills.utils import filter_schema
from skills.nodes import (
    sql_judge,
    human_approval,
    sql_executor,
    result_explainer
)
from skills.core import (
    detect_and_connect,
    read_schema_from_adapter,
    sql_generator
)


# ============================================================
# NODE 1.1: DETECT + CONNECT
# ============================================================

def node_connect(state: AgentState) -> AgentState:
    result = detect_and_connect(state["db_url"])

    state["db_type"] = result["db_type"]
    state["adapter"] = result["adapter"]

    print(f"[Node 1.1] Connected to: {state['db_type']}")

    return state


# ============================================================
# NODE 1.2: READ + FILTER SCHEMA
# ============================================================

def node_schema(state: AgentState) -> AgentState:
    full_schema = read_schema_from_adapter(
        state["adapter"]
    )

    print(f"[Node 1.2] Found {len(full_schema)} tables")

    state["schema_metadata"] = full_schema

    filtered_schema = filter_schema(
        full_schema,
        state["question"]
    )

    state["filtered_schema"] = filtered_schema

    print(
        f"[Node 1.2] After filtering: "
        f"{len(filtered_schema)} tables"
    )

    return state


# ============================================================
# NODE 2: SQL GENERATOR
# ============================================================

def node_generator(state: AgentState) -> AgentState:
    result = sql_generator(state)

    state.update(result)

    # Store generator metrics
    state["metrics"].update(
        result.get("metrics", {})
    )

    return state


# ============================================================
# NODE 3: LLM JUDGE
# ============================================================

def node_judge(state: AgentState) -> AgentState:
    result = sql_judge(state)

    state.update(result)

    # Store judge metrics
    state["metrics"].update(
        result.get("metrics", {})
    )

    # Count rejected Judge evaluations here.
    # This update happens inside a LangGraph node,
    # so the state is carried into the next node.
    if state.get("judge_approved") is not True:
        state["judge_attempts"] = (
            state.get("judge_attempts", 0) + 1
        )

    return state

# ============================================================
# NODE 4: HUMAN APPROVAL
# ============================================================

def node_human(state: AgentState) -> AgentState:
    """
    Node 4: Human-in-the-Loop.

    Normal mode:
        Human chooses:
            YES → Node 5
            Feedback → Node 2

    Skip-human mode:
        Automatically approve.
        Used for automated testing only.
    """

    if state.get("skip_human", False):

        print("[Node 4] Human approval skipped (test mode).")

        state["human_approved"] = True
        state["human_feedback"] = None
        state["status"] = "approved"

        return state

    result = human_approval(state)

    state.update(result)

    return state


# ============================================================
# NODE 5: QUERY EXECUTOR
# ============================================================

def node_executor(state: AgentState) -> AgentState:
    result = sql_executor(state)

    state.update(result)

    # Store execution metrics
    state["metrics"].update(
        result.get("metrics", {})
    )

    # Count failed executions inside the node
    # so LangGraph carries the updated state.
    if state.get("execution_error"):

        state["execution_attempts"] = (
            state.get("execution_attempts", 0) + 1
        )

    return state


# ============================================================
# NODE 6: RESULT EXPLAINER
# ============================================================

def node_explainer(state: AgentState) -> AgentState:
    result = result_explainer(state)

    state.update(result)

    return state


# ============================================================
# ROUTER AFTER NODE 3
# ============================================================

def route_after_judge(state: AgentState) -> str:
    """
    Judge approved:
        → Node 4 Human Approval

    Judge rejected:
        → Node 2 SQL Generator

    Maximum judge attempts:
        → END
    """

    # --------------------------------------------------------
    # Judge approved
    # --------------------------------------------------------

    if state.get("judge_approved") is True:
        return "node_human"

    # --------------------------------------------------------
    # Judge rejected
    # --------------------------------------------------------

    attempts = state.get(
        "judge_attempts",
        0
    )

    max_attempts = state.get(
        "max_judge_attempts",
        3
    )

    print(
        f"[Router] Judge rejected SQL. "
        f"Attempt {attempts}/{max_attempts}"
    )

    # --------------------------------------------------------
    # Maximum attempts
    # --------------------------------------------------------

    if attempts >= max_attempts:

        print(
            "[Router] ❌ Maximum judge attempts reached."
        )

        state["status"] = "judge_failed"

        return "end"

    # --------------------------------------------------------
    # Give feedback to Node 2
    # --------------------------------------------------------

    state["feedback"] = state.get(
        "judge_feedback",
        "SQL was rejected by the judge."
    )

    state["sql"] = None
    state["judge_approved"] = None

    return "node_generator"


# ============================================================
# ROUTER AFTER NODE 4
# ============================================================

def route_after_human(state: AgentState) -> str:
    """
    Human approved:
        → Node 5 Executor

    Human rejected:
        → Node 2 SQL Generator

    Maximum human attempts reached:
        → END
    """

    # --------------------------------------------------------
    # Human approved
    # --------------------------------------------------------

    if state.get("human_approved") is True:

        return "node_executor"

    # --------------------------------------------------------
    # Human rejected
    # --------------------------------------------------------

    feedback = state.get("human_feedback")

    if feedback:

        state["feedback"] = feedback

    state["human_attempts"] += 1

    print(
        f"[Router] Human rejected SQL. "
        f"Attempt {state['human_attempts']}/"
        f"{state['max_human_attempts']}"
    )

    # --------------------------------------------------------
    # Maximum human attempts reached
    # --------------------------------------------------------

    if (
        state["human_attempts"]
        >= state["max_human_attempts"]
    ):

        state["status"] = "human_failed"

        return "end"

    # --------------------------------------------------------
    # Loop back to Node 2
    # --------------------------------------------------------

    state["sql"] = None
    state["judge_approved"] = None
    state["human_approved"] = None

    return "node_generator"


# ============================================================
# ROUTER AFTER NODE 5
# ============================================================

def route_after_execution(state: AgentState) -> str:
    """
    Execution successful:
        → Node 6

    Execution failed:
        → Node 2 SQL Generator

    Maximum execution attempts:
        → END
    """

    # --------------------------------------------------------
    # Execution successful
    # --------------------------------------------------------

    if not state.get("execution_error"):
        return "node_explainer"

    # --------------------------------------------------------
    # Execution failed
    # --------------------------------------------------------

    attempts = state.get(
        "execution_attempts",
        0
    )

    max_attempts = state.get(
        "max_execution_attempts",
        3
    )

    print(
        f"[Router] Execution failed. "
        f"Attempt {attempts}/{max_attempts}"
    )

    # --------------------------------------------------------
    # Maximum attempts
    # --------------------------------------------------------

    if attempts >= max_attempts:

        print(
            "[Router] ❌ Maximum execution attempts reached."
        )

        state["status"] = "execution_failed"

        return "end"

    # --------------------------------------------------------
    # Give execution error to Node 2
    # --------------------------------------------------------

    state["feedback"] = state.get(
        "execution_error",
        "SQL execution failed."
    )

    state["sql"] = None
    state["judge_approved"] = None
    state["human_approved"] = None

    return "node_generator"

# ============================================================
# BUILD LANGGRAPH
# ============================================================

def build_graph():

    builder = StateGraph(AgentState)

    # --------------------------------------------------------
    # Add Nodes
    # --------------------------------------------------------

    builder.add_node(
        "node_connect",
        node_connect
    )

    builder.add_node(
        "node_schema",
        node_schema
    )

    builder.add_node(
        "node_generator",
        node_generator
    )

    builder.add_node(
        "node_judge",
        node_judge
    )

    builder.add_node(
        "node_human",
        node_human
    )

    builder.add_node(
        "node_executor",
        node_executor
    )

    builder.add_node(
        "node_explainer",
        node_explainer
    )

    # --------------------------------------------------------
    # Straight Edges
    # --------------------------------------------------------

    builder.add_edge(
        START,
        "node_connect"
    )

    builder.add_edge(
        "node_connect",
        "node_schema"
    )

    builder.add_edge(
        "node_schema",
        "node_generator"
    )

    builder.add_edge(
        "node_generator",
        "node_judge"
    )

    # --------------------------------------------------------
    # Node 3 → Node 2 / Node 4 / END
    # --------------------------------------------------------

    builder.add_conditional_edges(
        "node_judge",
        route_after_judge,
        {
            "node_generator": "node_generator",
            "node_human": "node_human",
            "end": END
        }
    )

    # --------------------------------------------------------
    # Node 4 → Node 2 / Node 5 / END
    # --------------------------------------------------------

    builder.add_conditional_edges(
        "node_human",
        route_after_human,
        {
            "node_generator": "node_generator",
            "node_executor": "node_executor",
            "end": END
        }
    )

    # --------------------------------------------------------
    # Node 5 → Node 2 / Node 6 / END
    # --------------------------------------------------------

    builder.add_conditional_edges(
        "node_executor",
        route_after_execution,
        {
            "node_generator": "node_generator",
            "node_explainer": "node_explainer",
            "end": END
        }
    )

    # --------------------------------------------------------
    # Node 6 → END
    # --------------------------------------------------------

    builder.add_edge(
        "node_explainer",
        END
    )

    return builder.compile()


# ============================================================
# RUN AGENT
# ============================================================

def run_agent(
    question: str,
    db_url: str = "postgresql://postgres:password@localhost:5433/ecommerce",
    demo_mode: bool = False,
    skip_human: bool = False,
    resume: bool = False,
    human_decision: dict = None,
    state: dict = None
) -> dict:

    # ========================================================
    # RESUME EXISTING RUN
    # ========================================================

    if resume and state:

        print("[Agent] Resuming previous state...")

        # ----------------------------------------------------
        # Apply human decision received from UI
        # ----------------------------------------------------

        if human_decision:

            if human_decision.get("approved"):

                state["human_approved"] = True
                state["human_feedback"] = None
                state["status"] = "approved"

            elif human_decision.get("feedback"):

                state["human_approved"] = False

                state["human_feedback"] = (
                    human_decision["feedback"]
                )

                state["feedback"] = (
                    human_decision["feedback"]
                )

                state["sql"] = None
                state["judge_approved"] = None
                state["status"] = "feedback"

            else:

                return {
                    "status": "human_rejected",
                    "error": "No valid human decision provided."
                }

        graph = build_graph()

        result = graph.invoke(state)

        return _format_result(result)

    # ========================================================
    # NEW RUN
    # ========================================================
    #
    # IMPORTANT:
    # Node 1.1 and Node 1.2 are NOT executed manually here.
    #
    # LangGraph starts at:
    #
    # START
    #   ↓
    # Node 1.1 Connect
    #   ↓
    # Node 1.2 Schema
    #   ↓
    # Node 2 Generator
    #
    # This keeps the complete workflow inside LangGraph.
    # ========================================================

    initial_state: AgentState = {

        "db_url": db_url,

        "db_type": "unknown",

        "adapter": None,

        "schema_metadata": None,

        "filtered_schema": None,

        "question": question,

        "sql": None,

        "feedback": None,

        # Node 2 informational counter
        "attempts": 0,

        # ----------------------------------------------------
        # Judge
        # ----------------------------------------------------

        "judge_approved": None,

        "judge_feedback": None,

        "judge_attempts": 0,

        "max_judge_attempts": 3,

        # ----------------------------------------------------
        # Human
        # ----------------------------------------------------

        "human_approved": None,

        "human_feedback": None,

        "human_attempts": 0,

        "max_human_attempts": 3,

        # ----------------------------------------------------
        # Execution
        # ----------------------------------------------------

        "execution_error": None,

        "execution_attempts": 0,

        "max_execution_attempts": 3,

        "data": None,

        "columns": None,

        # ----------------------------------------------------
        # Final result
        # ----------------------------------------------------

        "summary": None,

        "status": "starting",

        "metrics": {},

        # ----------------------------------------------------
        # Modes
        # ----------------------------------------------------

        "demo_mode": demo_mode,

        "skip_human": skip_human
    }

    # ========================================================
    # BUILD + INVOKE LANGGRAPH
    # ========================================================

    graph = build_graph()

    result = graph.invoke(initial_state)

    return _format_result(result)


# ============================================================
# FORMAT FINAL RESULT
# ============================================================

def _format_result(state: dict) -> dict:

    total_time = sum(
        state["metrics"].get(key, 0)
        for key in [
            "generator_latency",
            "judge_latency",
            "execution_time"
        ]
    )

    return {

        "sql": state.get("sql"),

        "data": state.get("data"),

        "columns": state.get("columns"),

        "summary": state.get("summary"),

        "status": state.get(
            "status",
            "success"
        ),

        "attempts": {

            "judge": state.get(
                "judge_attempts",
                0
            ),

            "human": state.get(
                "human_attempts",
                0
            ),

            "execution": state.get(
                "execution_attempts",
                0
            )

        },

        "metrics": {

            "generator_input_tokens":
                state["metrics"].get(
                    "generator_input_tokens",
                    0
                ),

            "generator_output_tokens":
                state["metrics"].get(
                    "generator_output_tokens",
                    0
                ),

            "generator_latency":
                state["metrics"].get(
                    "generator_latency",
                    0
                ),

            "judge_input_tokens":
                state["metrics"].get(
                    "judge_input_tokens",
                    0
                ),

            "judge_output_tokens":
                state["metrics"].get(
                    "judge_output_tokens",
                    0
                ),

            "judge_latency":
                state["metrics"].get(
                    "judge_latency",
                    0
                ),

            "execution_time":
                state["metrics"].get(
                    "execution_time",
                    0
                ),

            "total_time":
                total_time
        },

        "judge_approved":
            state.get("judge_approved"),

        "judge_feedback":
            state.get("judge_feedback"),

        "human_approved":
            state.get("human_approved"),

        "human_feedback":
            state.get("human_feedback"),

        "execution_error":
            state.get("execution_error")
    }

