# skills/state.py

from typing import TypedDict, List, Optional


class AgentState(TypedDict):

    # ========================================================
    # NODE 1
    # ========================================================

    db_url: str
    db_type: str
    adapter: Optional[object]

    # ========================================================
    # NODE 1.2
    # ========================================================

    schema_metadata: Optional[dict]
    filtered_schema: Optional[dict]

    # ========================================================
    # NODE 2
    # ========================================================

    question: str
    sql: Optional[str]
    feedback: Optional[str]
    attempts: int

    # ========================================================
    # NODE 3
    # ========================================================

    judge_approved: Optional[bool]
    judge_feedback: Optional[str]
    judge_attempts: int
    max_judge_attempts: int

    # ========================================================
    # NODE 4
    # ========================================================

    human_approved: Optional[bool]
    human_feedback: Optional[str]
    human_attempts: int
    max_human_attempts: int

    # ========================================================
    # NODE 5
    # ========================================================

    execution_error: Optional[str]
    execution_attempts: int
    max_execution_attempts: int

    data: Optional[List]
    columns: Optional[List[str]]
    row_count: int

    # ========================================================
    # NODE 6
    # ========================================================

    summary: Optional[str]

    # ========================================================
    # GENERAL
    # ========================================================

    status: str
    metrics: dict

    # ========================================================
    # TEST / DEMO
    # ========================================================

    demo_mode: bool
    skip_human: bool