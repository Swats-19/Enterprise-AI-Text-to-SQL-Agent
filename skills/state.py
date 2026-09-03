# skills/state.py

from typing import TypedDict, List, Optional, Any


class AgentState(TypedDict):
    """Shared state across all LangGraph nodes."""

    # ============================================================
    # NODE 1.1: DB TYPE DETECTION + CONNECTION
    # ============================================================

    db_url: str
    db_type: str
    adapter: Optional[object]

    # ============================================================
    # NODE 1.2: SCHEMA READER + FILTERING
    # ============================================================

    schema_metadata: Optional[dict]
    filtered_schema: Optional[dict]

    # ============================================================
    # NODE 2: SQL GENERATOR
    # ============================================================

    question: str
    sql: Optional[str]
    feedback: Optional[str]

    # Informational counter for SQL generation attempts
    attempts: int

    # ============================================================
    # NODE 3: LLM-AS-A-JUDGE
    # ============================================================

    judge_approved: Optional[bool]
    judge_feedback: Optional[str]

    judge_attempts: int
    max_judge_attempts: int

    # ============================================================
    # NODE 4: HUMAN APPROVAL
    # ============================================================

    human_approved: Optional[bool]
    human_feedback: Optional[str]

    human_attempts: int
    max_human_attempts: int

    # ============================================================
    # NODE 5: QUERY EXECUTION
    # ============================================================

    execution_error: Optional[str]

    execution_attempts: int
    max_execution_attempts: int

    data: Optional[List]
    columns: Optional[List[str]]

    # ============================================================
    # NODE 6: RESULT EXPLAINER
    # ============================================================

    summary: Optional[str]

    # ============================================================
    # GENERAL STATE
    # ============================================================

    status: str
    metrics: dict

    # ============================================================
    # TEST / DEMO CONTROL
    # ============================================================

    demo_mode: bool
    skip_human: bool