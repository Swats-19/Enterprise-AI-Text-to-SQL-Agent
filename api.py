import json
import os
from pathlib import Path
from threading import Lock
from typing import Any, Literal
from urllib.parse import urlsplit
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from database.factory import create_adapter
from llm import llm
from skills.orchestrator import run_agent


ROOT_DIR = Path(__file__).resolve().parent
ENV_PATH = ROOT_DIR / ".env"
load_dotenv(ENV_PATH, override=False)

app = FastAPI(title="Enterprise AI Text-to-SQL Agent")

_pending_approvals: dict[str, dict[str, str]] = {}
_pending_lock = Lock()


class StreamEventRequest(BaseModel):
    context_id: str
    human_query: str
    request_kind: Literal["default", "weekly_review"] = "default"


class DataSourceConnectRequest(BaseModel):
    provider: str
    connection_url: str


class ExecutionModeRequest(BaseModel):
    execution_mode: Literal["pro", "non_pro"]


class ApprovalActionRequest(BaseModel):
    reviewer_comment: str | None = None


def _sse_event(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=True, default=str)}\n\n"


def _database_url() -> str:
    return os.getenv("DATABASE_URL", "").strip()


def _execution_mode() -> str:
    mode = os.getenv("DEFAULT_EXECUTION_MODE", "pro").strip().lower()
    return mode if mode in {"pro", "non_pro"} else "pro"


def _database_label(database_url: str) -> str:
    if not database_url:
        return ""
    parsed = urlsplit(database_url)
    host = parsed.hostname or "localhost"
    port = f":{parsed.port}" if parsed.port else ""
    database = parsed.path.lstrip("/") or "database"
    return f"{host}{port}/{database}"


def _datasource_payload(message: str | None = None) -> dict[str, Any]:
    database_url = _database_url()
    mode = _execution_mode()
    return {
        "configured": bool(database_url),
        "provider": "postgres" if database_url else "",
        "database_label": _database_label(database_url),
        "message": message
        or (
            "PostgreSQL datasource connected."
            if database_url
            else "No datasource connected yet."
        ),
        "execution_mode": mode,
        "access_mode": "read_only",
    }


def _upsert_env_value(name: str, value: str) -> None:
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    prefix = f"{name}="
    replacement = f"{name}={value}"
    updated = False

    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = replacement
            updated = True
            break

    if not updated:
        lines.append(replacement)

    temporary_path = ENV_PATH.with_suffix(".env.tmp")
    temporary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    temporary_path.replace(ENV_PATH)
    os.environ[name] = value


def _result_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    columns = result.get("columns") or []
    rows = result.get("data") or []
    return [dict(zip(columns, row)) for row in rows]


def _todos(stage: str) -> list[dict[str, str]]:
    stages = [
        ("Discover database schema", "schema"),
        ("Generate SQL", "generate"),
        ("Judge SQL safety and correctness", "judge"),
        ("Request human approval", "approval"),
        ("Execute read-only query", "execute"),
        ("Summarize results", "summary"),
    ]
    order = [value for _, value in stages]
    active_index = order.index(stage) if stage in order else len(order)
    return [
        {
            "title": title,
            "content": title,
            "status": (
                "completed"
                if index < active_index
                else "in_progress"
                if index == active_index
                else "pending"
            ),
        }
        for index, (title, _) in enumerate(stages)
    ]


def _run_weekly_review(request: StreamEventRequest):
    yield _sse_event(
        "start",
        {"context_id": request.context_id, "message": "Weekly review started"},
    )
    yield _sse_event(
        "todos",
        {
            "context_id": request.context_id,
            "todos": [
                {
                    "title": "Summarize executed query history",
                    "content": "Summarize executed query history",
                    "status": "in_progress",
                }
            ],
        },
    )
    response = llm.invoke_generator(request.human_query)
    summary = response.get("content", "").strip()
    yield _sse_event(
        "final",
        {
            "context_id": request.context_id,
            "generated_sql": "",
            "query_result": [],
            "response_summary": summary,
            "todos": [
                {
                    "title": "Summarize executed query history",
                    "content": "Summarize executed query history",
                    "status": "completed",
                }
            ],
        },
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/datasource/status")
def datasource_status():
    return _datasource_payload()


@app.post("/datasource/connect")
def connect_datasource(request: DataSourceConnectRequest):
    if request.provider.strip().lower() not in {"postgres", "postgresql"}:
        raise HTTPException(status_code=400, detail="Only PostgreSQL is supported.")

    connection_url = request.connection_url.strip()
    try:
        adapter = create_adapter(connection_url)
        if not adapter.test_connection():
            raise ConnectionError("PostgreSQL rejected the connection.")
    except (ValueError, ConnectionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _upsert_env_value("DATABASE_URL", connection_url)
    return _datasource_payload("PostgreSQL datasource connected and saved.")


@app.post("/datasource/disconnect")
def disconnect_datasource():
    _upsert_env_value("DATABASE_URL", "")
    return _datasource_payload("Datasource disconnected.")


@app.post("/execution-mode")
def update_execution_mode(request: ExecutionModeRequest):
    _upsert_env_value("DEFAULT_EXECUTION_MODE", request.execution_mode)
    label = "Pro approval" if request.execution_mode == "pro" else "automatic approval"
    return _datasource_payload(f"{label} mode enabled. SQL execution remains read-only.")


@app.post("/deep-agent/stream")
def run_deep_agent_stream(request: StreamEventRequest):
    if not request.context_id.strip() or not request.human_query.strip():
        raise HTTPException(status_code=400, detail="context_id and human_query are required.")

    if request.request_kind == "weekly_review":
        return StreamingResponse(
            _run_weekly_review(request),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    database_url = _database_url()
    if not database_url:
        raise HTTPException(status_code=400, detail="Connect a PostgreSQL datasource first.")

    mode = _execution_mode()
    thread_id = f"{request.context_id}-{uuid4()}"

    def event_generator():
        yield _sse_event(
            "start",
            {"context_id": request.context_id, "message": "Agent run started"},
        )
        yield _sse_event(
            "todos",
            {"context_id": request.context_id, "todos": _todos("schema")},
        )
        yield _sse_event(
            "step",
            {
                "context_id": request.context_id,
                "source": "schema",
                "detail": "Connecting to PostgreSQL and discovering schema",
            },
        )

        try:
            result = run_agent(
                question=request.human_query,
                db_url=database_url,
                skip_human=mode == "non_pro",
                thread_id=thread_id,
            )
        except Exception as exc:
            yield _sse_event(
                "error",
                {"context_id": request.context_id, "message": str(exc)},
            )
            return

        sql = result.get("sql") or ""
        attempt = result.get("attempts", {}).get("judge", 1)
        feedback = result.get("judge_feedback") or ""

        if sql:
            yield _sse_event(
                "sql_generated",
                {
                    "context_id": request.context_id,
                    "sql": sql,
                    "attempt": attempt,
                    "source": "sql_generator",
                },
            )

        yield _sse_event(
            "judge_started",
            {
                "context_id": request.context_id,
                "attempt": attempt,
                "commentary": "SQL review completed.",
                "source": "sql_judge",
            },
        )

        judge_approved = (
            result.get("judge_approved") is True
            or result.get("status") == "needs_human_approval"
        )
        if judge_approved:
            yield _sse_event(
                "judge_approved",
                {
                    "context_id": request.context_id,
                    "attempt": attempt,
                    "commentary": feedback,
                    "reasons": [feedback] if feedback else [],
                    "source": "sql_judge",
                },
            )
        else:
            yield _sse_event(
                "judge_rejected",
                {
                    "context_id": request.context_id,
                    "attempt": attempt,
                    "commentary": feedback,
                    "reasons": [feedback] if feedback else [],
                    "source": "sql_judge",
                },
            )

        if result.get("status") == "needs_human_approval":
            approval_id = str(uuid4())
            with _pending_lock:
                _pending_approvals[approval_id] = {
                    "thread_id": result["thread_id"],
                    "context_id": request.context_id,
                }
            yield _sse_event(
                "todos",
                {"context_id": request.context_id, "todos": _todos("approval")},
            )
            yield _sse_event(
                "approval_required",
                {
                    "context_id": request.context_id,
                    "approval_id": approval_id,
                    "sql": sql,
                    "commentary": feedback or "Human approval is required before execution.",
                    "reasons": [feedback] if feedback else [],
                    "execution_mode": "pro",
                    "attempt": attempt,
                    "source": "human_approval",
                },
            )
            return

        if result.get("status") != "success":
            yield _sse_event(
                "error",
                {
                    "context_id": request.context_id,
                    "message": (
                        result.get("execution_error")
                        or result.get("judge_feedback")
                        or f"Agent stopped with status {result.get('status')}."
                    ),
                },
            )
            return

        yield _sse_event(
            "final",
            {
                "context_id": request.context_id,
                "generated_sql": sql,
                "query_result": _result_rows(result),
                "response_summary": result.get("summary") or "",
                "todos": _todos("done"),
            },
        )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/approvals/{approval_id}/approve")
def approve_pending_sql(
    approval_id: str,
    request: ApprovalActionRequest | None = None,
):
    with _pending_lock:
        pending = _pending_approvals.pop(approval_id, None)
    if not pending:
        raise HTTPException(
            status_code=404,
            detail="Pending approval not found or already resolved.",
        )

    result = run_agent(
        question="",
        resume=True,
        human_decision={"approved": True},
        thread_id=pending["thread_id"],
    )
    if result.get("status") == "needs_human_approval":
        next_approval_id = str(uuid4())
        with _pending_lock:
            _pending_approvals[next_approval_id] = {
                "thread_id": result["thread_id"],
                "context_id": pending["context_id"],
            }
        feedback = result.get("judge_feedback") or ""
        return {
            "status": "needs_human_approval",
            "approval_id": next_approval_id,
            "generated_sql": result.get("sql") or "",
            "judge_commentary": feedback,
            "judge_reasons": [feedback] if feedback else [],
            "execution_mode": "pro",
        }

    if result.get("status") != "success":
        raise HTTPException(
            status_code=400,
            detail=result.get("execution_error") or "Approved SQL execution failed.",
        )

    reviewer_comment = request.reviewer_comment if request else None
    return {
        "status": "approved",
        "approval_id": approval_id,
        "generated_sql": result.get("sql") or "",
        "query_result": _result_rows(result),
        "response_summary": result.get("summary") or "Approved SQL executed successfully.",
        "reviewer_note": reviewer_comment or "",
    }


@app.post("/approvals/{approval_id}/reject")
def reject_pending_sql(
    approval_id: str,
    request: ApprovalActionRequest | None = None,
):
    with _pending_lock:
        pending = _pending_approvals.pop(approval_id, None)
    if not pending:
        raise HTTPException(
            status_code=404,
            detail="Pending approval not found or already resolved.",
        )

    reviewer_comment = request.reviewer_comment if request else None
    message = "Human reviewer rejected the pending SQL execution."
    if reviewer_comment:
        message = f"{message} Reviewer note: {reviewer_comment}"
    return {
        "status": "rejected",
        "approval_id": approval_id,
        "response_summary": message,
    }
