# skills/orchestrator.py

from uuid import uuid4
import os

from database.factory import create_adapter

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

from skills.state import AgentState
from skills.utils import filter_schema

# IMPORTANT: import the node functions from your existing files
from skills.nodes import (
    sql_generator,
    sql_judge,
    sql_executor,
    result_explainer,
    detect_and_connect,
    read_schema_from_adapter
)


# ============================================================
# SHARED LANGGRAPH CHECKPOINTER
# ============================================================

checkpointer = MemorySaver()


# ============================================================
# NODE 1.1: DETECT + CONNECT
# ============================================================

def node_connect(state: AgentState) -> AgentState:
    result = detect_and_connect(state["db_url"])
    state["db_type"] = result["db_type"]
    print(f"[Node 1.1] Connected to: {state['db_type']}")
    return state


# ============================================================
# NODE 1.2: READ + FILTER SCHEMA
# ============================================================

def node_schema(state: AgentState) -> AgentState:
    # Create adapter locally (not stored in state)
    adapter = create_adapter(state["db_url"])
    full_schema = read_schema_from_adapter(adapter)
    print(f"[Node 1.2] Found {len(full_schema)} tables")

    state["schema_metadata"] = full_schema
    filtered_schema = filter_schema(full_schema, state["question"])
    state["filtered_schema"] = filtered_schema

    print(f"[Node 1.2] After filtering: {len(filtered_schema)} tables")
    return state


# ============================================================
# NODE 2: SQL GENERATOR
# ============================================================

def node_generator(state: AgentState) -> AgentState:
    result = sql_generator(state)
    state.update(result)
    # Store generator metrics
    state["metrics"].update(result.get("metrics", {}))
    return state


# ============================================================
# NODE 3: LLM JUDGE (UPDATED – counts every execution)
# ============================================================

def node_judge(state: AgentState) -> AgentState:
    # Increment attempt counter on every judge evaluation
    state["judge_attempts"] = state.get("judge_attempts", 0) + 1
    print(f"[Node 3] Judge evaluation #{state['judge_attempts']}")

    result = sql_judge(state)
    state.update(result)
    state["metrics"].update(result.get("metrics", {}))

    if state.get("judge_approved") is True:
        state["human_attempts"] = state.get("human_attempts", 0) + 1
    else:
        human_feedback = state.get("human_feedback")
        judge_feedback = state.get("judge_feedback")
        if human_feedback and judge_feedback:
            state["feedback"] = (
                f"Human requirement:\n{human_feedback}\n\n"
                f"Judge feedback:\n{judge_feedback}"
            )
        else:
            state["feedback"] = (
                human_feedback
                or judge_feedback
                or "SQL was rejected by the judge."
            )

        if state["judge_attempts"] >= state.get("max_judge_attempts", 3):
            state["status"] = "judge_failed"

    return state


# ============================================================
# NODE 4: HUMAN APPROVAL (UPDATED – uses interrupt)
# ============================================================

def node_human(state: AgentState) -> AgentState:
    """
    Node 4: Human-in-the-Loop.
    - skip_human: auto-approve (for testing)
    - Normal: interrupt() and wait for UI decision
    """
    if state.get("skip_human", False):
        print("[Node 4] Human approval skipped (test mode).")
        state["human_approved"] = True
        state["human_feedback"] = None
        state["status"] = "approved"
        return state

    # Real human‑in‑the‑loop
    decision = interrupt({
        "type": "human_approval",
        "sql": state.get("sql", ""),
        "question": state.get("question", ""),
        "judge_feedback": state.get("judge_feedback")
    })

    if isinstance(decision, dict) and decision.get("approved"):
        print("[Node 4] Human approved SQL.")
        state["human_approved"] = True
        state["human_feedback"] = None
        state["feedback"] = None
        state["status"] = "approved"
        return state

    if isinstance(decision, dict) and decision.get("feedback"):
        feedback = decision["feedback"]
        print(f"[Node 4] Human rejected SQL. Feedback: {feedback}")
        state["human_approved"] = False
        state["human_feedback"] = feedback
        state["feedback"] = feedback
        state["sql"] = None
        state["judge_approved"] = None
        state["judge_feedback"] = None
        state["status"] = "feedback"
        return state

    # Invalid decision
    state["human_approved"] = False
    state["human_feedback"] = "Invalid human decision. Please regenerate the SQL."
    state["feedback"] = state["human_feedback"]
    state["sql"] = None
    state["judge_approved"] = None
    state["judge_feedback"] = None
    state["status"] = "feedback"
    return state


# ============================================================
# NODE 5: QUERY EXECUTOR (UPDATED – counts every execution)
# ============================================================

def node_executor(state: AgentState) -> AgentState:
    # Increment attempt counter on every execution attempt
    state["execution_attempts"] = state.get("execution_attempts", 0) + 1
    print(f"[Node 5] Execution attempt #{state['execution_attempts']}")

    # Create a temporary adapter for this execution only
    exec_state = dict(state)
    exec_state["adapter"] = create_adapter(state["db_url"])

    result = sql_executor(exec_state)
    state.update(result)
    state["metrics"].update(result.get("metrics", {}))

    if state.get("execution_error"):
        state["feedback"] = state["execution_error"]
        state["judge_approved"] = None
        state["human_approved"] = None
        if state["execution_attempts"] >= state.get("max_execution_attempts", 3):
            state["status"] = "execution_failed"

    return state


# ============================================================
# NODE 6: RESULT EXPLAINER
# ============================================================

def node_explainer(state: AgentState) -> AgentState:
    result = result_explainer(state)
    state.update(result)
    return state


# ============================================================
# ROUTER AFTER NODE 3 (UPDATED – counts human cycle)
# ============================================================

def route_after_judge(state: AgentState) -> str:
    if state.get("judge_approved") is True:
        print(f"[Router] Human approval #{state['human_attempts']} begins.")
        return "node_human"

    # Judge rejected
    attempts = state.get("judge_attempts", 0)
    max_attempts = state.get("max_judge_attempts", 3)

    if attempts >= max_attempts:
        return "end"

    return "node_generator"


# ============================================================
# ROUTER AFTER NODE 4 (UPDATED – no increment)
# ============================================================

def route_after_human(state: AgentState) -> str:
    if state.get("human_approved") is True:
        print(f"[Router] Human approved (attempt #{state.get('human_attempts', 0)})")
        return "node_executor"

    # Human rejected or gave feedback
    if state.get("human_feedback"):
        state["feedback"] = state["human_feedback"]

    attempts = state.get("human_attempts", 0)
    max_attempts = state.get("max_human_attempts", 3)

    if attempts >= max_attempts:
        return "end"

    return "node_generator"


# ============================================================
# ROUTER AFTER NODE 5
# ============================================================

def route_after_execution(state: AgentState) -> str:
    if not state.get("execution_error"):
        return "node_explainer"

    attempts = state.get("execution_attempts", 0)
    max_attempts = state.get("max_execution_attempts", 3)

    if attempts >= max_attempts:
        return "end"

    return "node_generator"


# ============================================================
# BUILD LANGGRAPH
# ============================================================

def build_graph():
    builder = StateGraph(AgentState)

    builder.add_node("node_connect", node_connect)
    builder.add_node("node_schema", node_schema)
    builder.add_node("node_generator", node_generator)
    builder.add_node("node_judge", node_judge)
    builder.add_node("node_human", node_human)
    builder.add_node("node_executor", node_executor)
    builder.add_node("node_explainer", node_explainer)

    builder.add_edge(START, "node_connect")
    builder.add_edge("node_connect", "node_schema")
    builder.add_edge("node_schema", "node_generator")
    builder.add_edge("node_generator", "node_judge")

    builder.add_conditional_edges(
        "node_judge",
        route_after_judge,
        {
            "node_generator": "node_generator",
            "node_human": "node_human",
            "end": END
        }
    )

    builder.add_conditional_edges(
        "node_human",
        route_after_human,
        {
            "node_generator": "node_generator",
            "node_executor": "node_executor",
            "end": END
        }
    )

    builder.add_conditional_edges(
        "node_executor",
        route_after_execution,
        {
            "node_generator": "node_generator",
            "node_explainer": "node_explainer",
            "end": END
        }
    )

    builder.add_edge("node_explainer", END)

    return builder.compile(checkpointer=checkpointer)


# ============================================================
# RUN AGENT
# ============================================================

def run_agent(
    question: str,
    db_url: str = None,
    demo_mode: bool = False,
    skip_human: bool = False,
    resume: bool = False,
    human_decision: dict = None,
    state: dict = None,
    thread_id: str = None
) -> dict:

    db_url = db_url or os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError(
            "DATABASE_URL is required. Add it to .env or pass db_url explicitly."
        )

    if thread_id is None:
        thread_id = str(uuid4())

    config = {"configurable": {"thread_id": thread_id}}
    graph = build_graph()

    # ============================================================
    # RESUME EXISTING RUN
    # ============================================================
    if resume:
        print(f"[Agent] Resuming LangGraph thread: {thread_id}")
        if not human_decision:
            return {
                "status": "human_rejected",
                "error": "No human decision provided.",
                "thread_id": thread_id
            }

        result = graph.invoke(Command(resume=human_decision), config=config)

        if "__interrupt__" in result:
            return _format_interrupted_result(result, thread_id, graph)

        return _format_result(result, thread_id)

    # ============================================================
    # NEW RUN
    # ============================================================
    initial_state: AgentState = {
        "db_url": db_url,
        "db_type": "unknown",
        "adapter": None,
        "schema_metadata": None,
        "filtered_schema": None,
        "question": question,
        "sql": None,
        "feedback": None,

        # Generator (no max)
        "attempts": 0,

        # Judge
        "judge_approved": None,
        "judge_feedback": None,
        "judge_attempts": 0,
        "max_judge_attempts": 3,

        # Human
        "human_approved": None,
        "human_feedback": None,
        "human_attempts": 0,
        "max_human_attempts": 3,

        # Execution
        "execution_error": None,
        "execution_attempts": 0,
        "max_execution_attempts": 3,

        "data": None,
        "columns": None,
        "row_count": 0,

        # Final
        "summary": None,
        "status": "starting",
        "metrics": {},

        # Modes
        "demo_mode": demo_mode,
        "skip_human": skip_human
    }

    result = graph.invoke(initial_state, config=config)

    if "__interrupt__" in result:
        return _format_interrupted_result(result, thread_id, graph)

    return _format_result(result, thread_id)


# ============================================================
# FORMAT INTERRUPTED RESULT
# ============================================================

def _format_interrupted_result(result: dict, thread_id: str, graph) -> dict:
    interrupts = result.get("__interrupt__", [])
    if not interrupts:
        return {"status": "needs_human_approval", "thread_id": thread_id}

    interrupt_value = interrupts[0].value
    config = {"configurable": {"thread_id": thread_id}}
    current_state = graph.get_state(config).values

    return {
        "status": "needs_human_approval",
        "thread_id": thread_id,
        "sql": current_state.get("sql"),
        "question": current_state.get("question"),
        "judge_feedback": current_state.get("judge_feedback"),
        "interrupt": interrupt_value,
        "state": current_state
    }


# ============================================================
# FORMAT FINAL RESULT
# ============================================================

def _format_result(state: dict, thread_id: str = None) -> dict:
    metrics = state.get("metrics", {})
    total_time = sum(
        metrics.get(key, 0)
        for key in ["generator_latency", "judge_latency", "execution_time"]
    )

    return {
        "sql": state.get("sql"),
        "data": state.get("data"),
        "columns": state.get("columns"),
        "summary": state.get("summary"),
        "status": state.get("status", "success"),
        "thread_id": thread_id,
        "attempts": {
            "judge": state.get("judge_attempts", 0),
            "human": state.get("human_attempts", 0),
            "execution": state.get("execution_attempts", 0)
        },
        "metrics": {
            "generator_input_tokens": metrics.get("generator_input_tokens", 0),
            "generator_output_tokens": metrics.get("generator_output_tokens", 0),
            "generator_latency": metrics.get("generator_latency", 0),
            "judge_input_tokens": metrics.get("judge_input_tokens", 0),
            "judge_output_tokens": metrics.get("judge_output_tokens", 0),
            "judge_latency": metrics.get("judge_latency", 0),
            "execution_time": metrics.get("execution_time", 0),
            "total_time": total_time
        },
        "judge_approved": state.get("judge_approved"),
        "judge_feedback": state.get("judge_feedback"),
        "human_approved": state.get("human_approved"),
        "human_feedback": state.get("human_feedback"),
        "execution_error": state.get("execution_error")
    }