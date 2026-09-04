import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import type { JudgeTranscriptEntry, PendingApproval, StreamEnvelope, StreamLog, StreamState, TodoItem, TodoStatus } from "./types";

const initialState: StreamState = {
  status: "idle",
  todos: [],
  logs: [],
  generatedSql: "",
  responseSummary: "",
  queryResult: [],
  latestError: "",
  judgeStatus: "idle",
  judgeReasons: [],
  judgeCommentary: "",
  judgeTranscript: [],
};

type DataSourceState = {
  configured: boolean;
  provider: string;
  databaseLabel: string;
  message: string;
  executionMode: "pro" | "non_pro";
  accessMode: "read_only" | "write_enabled";
  status: "idle" | "saving" | "disconnecting" | "connected" | "updating_mode" | "error";
};

const initialDataSourceState: DataSourceState = {
  configured: false,
  provider: "",
  databaseLabel: "",
  message: "No datasource connected yet.",
  executionMode: "non_pro",
  accessMode: "write_enabled",
  status: "idle",
};

type ThemeMode = "dark" | "light";

type ContextRunHistoryEntry = {
  id: string;
  title: string;
  userQuery: string;
  generatedSql: string;
  responseSummary: string;
  rowCount: number;
  executedAt: string;
  requestKind: "default" | "weekly_review";
};

type ContextHistoryEntry = {
  id: string;
  title: string;
  lastQuery: string;
  updatedAt: string;
  snapshot: StreamState;
  runHistory: ContextRunHistoryEntry[];
};

const CONTEXT_HISTORY_KEY = "alchemy-context-history";

function getInitialTheme(): ThemeMode {
  if (typeof window === "undefined") {
    return "dark";
  }

  const savedTheme = window.localStorage.getItem("alchemy-theme");
  if (savedTheme === "dark" || savedTheme === "light") {
    return savedTheme;
  }

  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

function createContextId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `ctx-${Date.now()}`;
}

function loadContextHistory(): ContextHistoryEntry[] {
  if (typeof window === "undefined") {
    return [];
  }

  try {
    const raw = window.localStorage.getItem(CONTEXT_HISTORY_KEY);
    if (!raw) {
      return [];
    }

    const parsed = JSON.parse(raw) as ContextHistoryEntry[];
    if (!Array.isArray(parsed)) {
      return [];
    }

    const seen = new Set<string>();
    return parsed.filter((entry) => {
      if (!entry || typeof entry.id !== "string" || seen.has(entry.id)) {
        return false;
      }
      seen.add(entry.id);
      entry.snapshot = normalizeStoredSnapshot(entry.snapshot);
      entry.runHistory = Array.isArray(entry.runHistory) ? entry.runHistory : [];
      return true;
    });
  } catch {
    return [];
  }
}

function buildContextTitle(query: string, contextId: string) {
  const compact = query.trim().replace(/\s+/g, " ");
  return compact ? compact.slice(0, 44) : `Conversation ${contextId.slice(0, 8)}`;
}

function buildRunningSnapshot(contextId: string): StreamState {
  return {
    ...initialState,
    status: "running",
    logs: appendLog([], "request", `Question submitted for context ${contextId}`),
  };
}

function parseSseEvent(rawEvent: string): StreamEnvelope | null {
  const normalized = rawEvent.replace(/\r/g, "").trim();
  if (!normalized) {
    return null;
  }

  let event = "message";
  const dataLines: string[] = [];

  for (const line of normalized.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }

  const rawData = dataLines.join("\n");
  if (!rawData) {
    return { event, data: null };
  }

  try {
    return { event, data: JSON.parse(rawData) };
  } catch {
    return { event, data: rawData };
  }
}

async function readJsonPayload(response: Response): Promise<Record<string, unknown>> {
  const rawText = await response.text();
  if (!rawText.trim()) {
    return {};
  }

  try {
    const parsed = JSON.parse(rawText) as unknown;
    return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : {};
  } catch {
    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}. The server returned an invalid response.`);
    }

    throw new Error("The server returned an invalid response.");
  }
}

async function streamDeepAgent(
  payload: { context_id: string; human_query: string; request_kind?: "default" | "weekly_review" },
  signal: AbortSignal,
  onEvent: (event: StreamEnvelope) => void,
) {
  const response = await fetch("/api/deep-agent/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(payload),
    signal,
  });

  if (!response.ok) {
    throw new Error(`Stream request failed with status ${response.status}`);
  }

  if (!response.body) {
    throw new Error("Streaming response body is unavailable in this browser.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });

    while (buffer.includes("\n\n")) {
      const boundary = buffer.indexOf("\n\n");
      const rawEvent = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);

      const parsed = parseSseEvent(rawEvent);
      if (parsed) {
        onEvent(parsed);
      }
    }
  }

  if (buffer.trim()) {
    const parsed = parseSseEvent(buffer);
    if (parsed) {
      onEvent(parsed);
    }
  }
}

function appendLog(logs: StreamLog[], type: string, message: string, source?: string) {
  return [
    {
      id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      type,
      source,
      message,
      timestamp: new Date().toLocaleTimeString(),
    },
    ...logs,
  ].slice(0, 60);
}

function getTimelineTypeLabel(type: string) {
  switch (type) {
    case "request":
      return "Request submitted";
    case "start":
      return "Agent started";
    case "step":
      return "Execution update";
    case "todos":
      return "Plan updated";
    case "llm_reasoning":
      return "Drafting response";
    case "sql_generated":
      return "SQL drafted";
    case "judge_started":
      return "LLM Judge review started";
    case "judge_approved":
      return "LLM Judge approved SQL";
    case "judge_rejected":
      return "LLM Judge requested changes";
    case "approval_required":
      return "Waiting for human approval";
    case "final":
      return "Run completed";
    case "error":
      return "Run failed";
    default:
      return type;
  }
}

function appendJudgeTranscript(
  transcript: JudgeTranscriptEntry[],
  speaker: JudgeTranscriptEntry["speaker"],
  message: string,
  side: JudgeTranscriptEntry["side"],
  tone: JudgeTranscriptEntry["tone"] = "neutral",
) {
  return [
    ...transcript,
    {
      id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      speaker,
      side,
      tone,
      message,
      timestamp: new Date().toLocaleTimeString(),
    },
  ].slice(-24);
}

function normalizeTodoLabel(todo: TodoItem) {
  return todo.content || todo.title || todo.description || "Untitled task";
}

function finalizeTodos(todos: TodoItem[]) {
  return todos.map((todo) => ({ ...todo, status: "completed" }));
}

function failOpenTodos(todos: TodoItem[]) {
  return todos.map((todo) => (todo.status === "completed" ? todo : { ...todo, status: "failed" }));
}

function isRetrySignalText(value: string) {
  return /retry|corrected sql|trying again|re-attempt/i.test(value);
}

function getSqlStatementCount(sql: string) {
  return sql
    .split(";")
    .map((statement) => statement.trim())
    .filter(Boolean).length;
}

type StatementGroup = {
  key: string;
  label: string;
  sql?: string;
  rows: Array<Record<string, unknown>>;
  isCombined?: boolean;
};

type CombinedDataset = {
  key: string;
  label: string;
  rows: Array<Record<string, unknown>>;
  columns: string[];
};

function splitSqlStatements(sql: string) {
  return (sql.match(/[\s\S]*?;(?:\s*|$)|[\s\S]+$/g) ?? []).filter((segment) => segment.trim().length > 0);
}

function normalizeStoredSnapshot(snapshot: Partial<StreamState> | undefined): StreamState {
  return {
    ...initialState,
    ...snapshot,
    todos: Array.isArray(snapshot?.todos) ? snapshot.todos : initialState.todos,
    logs: Array.isArray(snapshot?.logs) ? snapshot.logs : initialState.logs,
    queryResult: Array.isArray(snapshot?.queryResult) ? snapshot.queryResult : initialState.queryResult,
    judgeReasons: Array.isArray(snapshot?.judgeReasons) ? snapshot.judgeReasons : initialState.judgeReasons,
    judgeTranscript: Array.isArray(snapshot?.judgeTranscript) ? snapshot.judgeTranscript : initialState.judgeTranscript,
  };
}

function buildWeeklyReviewPrompt(contextId: string, runHistory: ContextRunHistoryEntry[]) {
  const executedRuns = runHistory.filter((run) => run.generatedSql.trim() || run.responseSummary.trim());
  const runHistoryLines = executedRuns.map((run, index) => {
    return [
      `${index + 1}. Executed at: ${run.executedAt}`,
      `Request label: ${run.title}`,
      `User query: ${run.userQuery || "[none]"}`,
      `Generated SQL: ${run.generatedSql || "[none]"}`,
      `Rows returned: ${run.rowCount}`,
      `Execution summary: ${run.responseSummary || "[none]"}`,
    ].join(" | ");
  });

  const promptSections = [
    "Generate a weekly review report for the current Text-to-SQL agent context.",
    `Context ID: ${contextId}`,
    "Weekly review means a collection of summaries of all executed queries for this context ID.",
    "Use only executed SQL outcomes and user-facing query summaries. Ignore judge comments, rejected SQL, approval chatter, retries that were not executed, and any non-executed attempts.",
    "If the context memory contains more executed-query history than the list below, you may use it, but keep the report focused only on executed SQL results.",
    "Start a fresh run from schema discovery and produce a concise weekly review report grounded in executed query history for this context. If needed, run a fresh read-only SQL query to verify or consolidate the report.",
    "Response format rules: start directly with 'Weekly Review:' and then the report content. Do not mention internal limitations, missing archived history, UI history, local storage, prompt instructions, fallback logic, or that you had to use a fresh snapshot. Do not say 'No prior executed-query history was available'.",
    `Executed query history: ${runHistoryLines.length > 0 ? runHistoryLines.join(" || ") : "[No archived executions provided. Use context memory and, if needed, a fresh read-only verification query, but do not mention this fallback in the final answer.]"}`,
  ];

  return promptSections.join("\n\n");
}

function splitInsightSegments(summary: string) {
  const trimmed = summary.trim();
  if (!trimmed) {
    return [];
  }

  const paragraphChunks = trimmed
    .split(/\n+/)
    .map((chunk) => chunk.trim())
    .filter(Boolean);

  if (paragraphChunks.length > 1) {
    return paragraphChunks;
  }

  const sentenceChunks = trimmed.match(/[^.!?\n]+[.!?]?/g)?.map((chunk) => chunk.trim()).filter(Boolean) ?? [];
  return sentenceChunks.length > 0 ? sentenceChunks : [trimmed];
}

function buildStatementInsights(summary: string, statementCount: number) {
  const segments = splitInsightSegments(summary);
  if (statementCount <= 1) {
    return [summary.trim()];
  }

  const count = Math.max(statementCount, 1);
  if (segments.length === 0) {
    return Array.from({ length: count }, () => "");
  }

  const insights = Array.from({ length: count }, () => [] as string[]);
  segments.forEach((segment, index) => {
    insights[Math.min(index, count - 1)].push(segment);
  });

  return insights.map((chunks, index) => {
    if (chunks.length > 0) {
      return chunks.join(" ");
    }

    return segments[Math.min(index, segments.length - 1)] ?? "";
  });
}

function getTypedStatementChunks(sql: string, typedSql: string) {
  const chunks = splitSqlStatements(sql);
  let consumed = 0;

  return chunks.map((chunk) => {
    const visibleLength = Math.max(0, Math.min(chunk.length, typedSql.length - consumed));
    const visible = chunk.slice(0, visibleLength);
    consumed += chunk.length;
    return visible;
  });
}

const SQL_KEYWORDS = new Set([
  "select",
  "from",
  "join",
  "inner",
  "left",
  "right",
  "full",
  "outer",
  "cross",
  "on",
  "where",
  "order",
  "by",
  "group",
  "having",
  "limit",
  "offset",
  "insert",
  "into",
  "update",
  "delete",
  "values",
  "as",
  "and",
  "or",
  "not",
  "null",
  "is",
  "case",
  "when",
  "then",
  "else",
  "end",
  "distinct",
  "union",
  "all",
  "asc",
  "desc",
]);

function renderHighlightedSql(sqlText: string) {
  const tokens = sqlText.match(/\s+|--.*?$|\/\*[\s\S]*?\*\/|'(?:''|[^'])*'|"(?:""|[^"])*"|\b[a-z_][a-z0-9_$]*\b|\d+(?:\.\d+)?|./gim) ?? [sqlText];

  return tokens.map((token, index) => {
    if (/^\s+$/.test(token)) {
      return token;
    }

    const normalized = token.toLowerCase();
    let className = "sql-token";

    if (SQL_KEYWORDS.has(normalized)) {
      className += " sql-token-keyword";
    } else if (/^['"]/.test(token)) {
      className += " sql-token-string";
    } else if (/^\d/.test(token)) {
      className += " sql-token-number";
    } else if (/^[(),.;]$/.test(token)) {
      className += " sql-token-punctuation";
    } else if (/^(=|<>|!=|<=|>=|<|>|\+|-|\*|\/)$/.test(token)) {
      className += " sql-token-operator";
    }

    return (
      <span key={`${token}-${index}`} className={className}>
        {token}
      </span>
    );
  });
}

function serializeResultRows(rows: Array<Record<string, unknown>>, columns: string[]) {
  if (rows.length === 0 || columns.length === 0) {
    return "";
  }

  const escapeCell = (value: unknown) => {
    const stringValue = formatResultValueForCopy(value);
    if (!/[",\n\t]/.test(stringValue)) {
      return stringValue;
    }
    return `"${stringValue.replace(/"/g, '""')}"`;
  };

  const lines = [columns.join("\t")];
  rows.forEach((row) => {
    lines.push(columns.map((column) => escapeCell(row[column])).join("\t"));
  });
  return lines.join("\n");
}

function formatResultValueForCopy(value: unknown): string {
  if (value == null) {
    return "";
  }

  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }

  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function formatResultPrimitive(value: unknown) {
  if (value == null) {
    return "--";
  }

  if (typeof value === "string") {
    return value;
  }

  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }

  return formatResultValueForCopy(value);
}

function renderObjectEntries(value: Record<string, unknown>) {
  return (
    <div className="result-object-grid">
      {Object.entries(value).map(([key, nestedValue]) => (
        <div key={key} className="result-object-item">
          <span className="result-object-key">{key}</span>
          <span className="result-object-value">{formatResultPrimitive(nestedValue)}</span>
        </div>
      ))}
    </div>
  );
}

function renderResultCell(value: unknown): JSX.Element | string {
  if (value == null) {
    return <span className="result-empty-value">--</span>;
  }

  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <span className="result-empty-value">[]</span>;
    }

    if (value.every((item) => item == null || typeof item === "string" || typeof item === "number" || typeof item === "boolean")) {
      return (
        <div className="result-pill-list">
          {value.map((item, index) => (
            <span key={`${String(item)}-${index}`} className="result-pill">
              {formatResultPrimitive(item)}
            </span>
          ))}
        </div>
      );
    }

    if (value.every((item) => item && typeof item === "object" && !Array.isArray(item))) {
      return (
        <div className="result-nested-stack">
          {value.map((item, index) => (
            <div key={`nested-${index}`} className="result-nested-card">
              <span className="result-nested-label">Item {index + 1}</span>
              {renderObjectEntries(item as Record<string, unknown>)}
            </div>
          ))}
        </div>
      );
    }

    return <pre className="result-json-block">{formatResultValueForCopy(value)}</pre>;
  }

  if (typeof value === "object") {
    return renderObjectEntries(value as Record<string, unknown>);
  }

  return String(value);
}

function titleCaseDatasetLabel(value: string) {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function buildCombinedDatasets(rows: Array<Record<string, unknown>>): CombinedDataset[] {
  if (rows.length !== 1) {
    return [];
  }

  const [container] = rows;
  const datasets: CombinedDataset[] = [];

  Object.entries(container).forEach(([key, value]) => {
    if (isRecordArray(value)) {
      const columns = Array.from(new Set(value.flatMap((row) => Object.keys(row))));
      datasets.push({
        key,
        label: titleCaseDatasetLabel(key),
        rows: value,
        columns,
      });
      return;
    }

    if (value && typeof value === "object" && !Array.isArray(value)) {
      const row = value as Record<string, unknown>;
      datasets.push({
        key,
        label: titleCaseDatasetLabel(key),
        rows: [row],
        columns: Object.keys(row),
      });
    }
  });

  return datasets;
}

function isRecordArray(value: unknown): value is Array<Record<string, unknown>> {
  return Array.isArray(value) && value.every((item) => item && typeof item === "object" && !Array.isArray(item));
}

function stripStatementMeta(row: Record<string, unknown>) {
  const clone = { ...row };
  delete clone.statement_index;
  delete clone.statement_number;
  delete clone.statement_id;
  delete clone.statement_label;
  delete clone.statement_sql;
  return clone;
}

function buildStatementGroups(rows: Array<Record<string, unknown>>, sql: string): StatementGroup[] {
  const statements = splitSqlStatements(sql).map((statement) => statement.trim());

  if (rows.length === 0) {
    return statements.map((statement, index) => ({
      key: `statement-${index + 1}`,
      label: `Statement ${index + 1}`,
      sql: statement,
      rows: [],
    }));
  }

  if (rows.every((row) => isRecordArray(row.rows))) {
    return rows.map((row, index) => ({
      key: `statement-group-${index + 1}`,
      label: typeof row.statement_label === "string" ? row.statement_label : `Statement ${Number(row.statement_index ?? index + 1)}`,
      sql: typeof row.statement_sql === "string" ? row.statement_sql : statements[index],
      rows: (row.rows as Array<Record<string, unknown>>) ?? [],
    }));
  }

  const rowsWithIndex = rows.filter((row) => row.statement_index != null || row.statement_number != null || row.statement_id != null);
  if (rowsWithIndex.length === rows.length) {
    const grouped = new Map<string, StatementGroup>();
    rows.forEach((row, index) => {
      const rawIndex = row.statement_index ?? row.statement_number ?? row.statement_id ?? index + 1;
      const numericIndex = Number(rawIndex);
      const key = String(rawIndex);
      if (!grouped.has(key)) {
        grouped.set(key, {
          key,
          label: typeof row.statement_label === "string" ? row.statement_label : `Statement ${Number.isFinite(numericIndex) ? numericIndex : index + 1}`,
          sql: typeof row.statement_sql === "string" ? row.statement_sql : statements[(Number.isFinite(numericIndex) ? numericIndex : index + 1) - 1],
          rows: [],
        });
      }
      grouped.get(key)?.rows.push(stripStatementMeta(row));
    });
    return Array.from(grouped.values());
  }

  if (statements.length > 1) {
    return [
      {
        key: "combined-result",
        label: "Combined result",
        rows,
        isCombined: true,
      },
    ];
  }

  return [
    {
      key: "statement-1",
      label: "Statement 1",
      sql: statements[0],
      rows,
    },
  ];
}

function getStatusConfig(status: TodoStatus) {
  switch (status) {
    case "completed":
      return { icon: "✓", className: "todo completed", caption: "Completed" };
    case "failed":
      return { icon: "!", className: "todo failed", caption: "Failed" };
    case "in_progress":
      return { icon: "..", className: "todo active", caption: "In progress" };
    default:
      return { icon: "--", className: "todo pending", caption: "Pending" };
  }
}

function ThinkingDots() {
  return (
    <span className="thinking-dots" aria-label="Processing">
      <span />
      <span />
      <span />
    </span>
  );
}

function WorkflowAgentIcon() {
  return (
    <svg viewBox="0 0 36 36" className="workflow-agent-icon" aria-hidden="true">
      <path className="workflow-agent-antenna" d="M18 5V2.8" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <rect className="workflow-agent-shell" x="9" y="7" width="18" height="12" rx="6" fill="rgba(142,243,255,0.16)" stroke="currentColor" strokeWidth="1.8" />
      <circle className="workflow-agent-eye" cx="14" cy="13" r="1.6" fill="currentColor" />
      <circle className="workflow-agent-eye" cx="22" cy="13" r="1.6" fill="currentColor" />
      <path className="workflow-agent-smile" d="M12 24c2.1 2 9.9 2 12 0" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path className="workflow-agent-limb arm-left" d="M13.4 18.6l-3.2 2.8" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path className="workflow-agent-limb arm-right" d="M22.6 18.6l3.2 2.8" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path className="workflow-agent-limb leg-left" d="M14 19v6M12.2 26.6l-2.4 4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path className="workflow-agent-limb leg-right" d="M22 19v6M23.8 26.6l2.4 4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ClockIcon() {
  return (
    <svg viewBox="0 0 20 20" className="timeline-clock-icon" aria-hidden="true">
      <circle cx="10" cy="10" r="7" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <path d="M10 6.2v4.1l2.8 1.7" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function isRateLimitFailure(message: string) {
  return /\b429\b|too many requests|too_many_requests/i.test(message);
}

function getFailureCopy(message: string) {
  if (isRateLimitFailure(message)) {
    return {
      primary: "The LLM provider rate-limited this run before judge review or SQL execution could finish.",
      secondary: "This is an upstream model throttle rather than a SQL-policy failure. Retry after a short pause, or reduce rapid repeated runs against the same model deployment.",
    };
  }

  return {
    primary: message,
    secondary: "The run stopped before a valid final answer was completed. Use the timeline to inspect the exact failure step.",
  };
}

function getJudgeSpeakerMeta(speaker: string) {
  if (speaker === "judge") {
    return { label: "Judge" };
  }

  if (speaker === "llm") {
    return { label: "Query Generator" };
  }

  return { label: speaker };
}

function getJudgeAttemptLabel(attempt: unknown) {
  return typeof attempt === "number" && Number.isFinite(attempt) && attempt > 0 ? `Attempt ${attempt}` : "Current attempt";
}

function formatJudgeSqlReviewMessage(attempt: unknown, sql: string) {
  const attemptLabel = getJudgeAttemptLabel(attempt);
  return `${attemptLabel}: Query Generated`;
}

function formatJudgeAwaitingMessage(attempt: unknown) {
  return `${getJudgeAttemptLabel(attempt)}: Waiting for LLM as a Judge Verdict`;
}

function formatJudgeApprovedMessage(attempt: unknown, commentary: string) {
  const prefix = `${getJudgeAttemptLabel(attempt)}:`;
  return commentary.trim() ? `${prefix} ${commentary.trim()}` : `${prefix} Approved. Executing SQL.`;
}

function formatJudgeRejectedMessage(attempt: unknown, commentary: string, reasons: string[]) {
  const reasonText = commentary.trim() || reasons.join("; ") || "Query rejected.";
  return `${getJudgeAttemptLabel(attempt)}: JUDGE COMMENTS: ${reasonText}`;
}

function formatJudgeRegenerationMessage(nextAttempt: unknown) {
  return `${getJudgeAttemptLabel(nextAttempt)}: Re-Generating SQL`;
}

function formatHumanApprovalMessage(attempt: unknown, commentary: string) {
  const prefix = `${getJudgeAttemptLabel(attempt)}:`;
  const resolved = commentary.trim() || "Human approval required before execution in pro mode.";
  return `${prefix} ${resolved}`;
}

function formatHumanApprovalExecutionMessage() {
  return "Human approval received. Executing approved SQL.";
}

function formatHumanRejectionMessage() {
  return "Human reviewer rejected the pending SQL execution.";
}

function buildHumanRejectionFollowupQuery(originalQuery: string, rejectedSql: string, feedback: string) {
  return [
    originalQuery.trim(),
    "Human reviewer rejected the previous Pro-mode SQL approval request.",
    `Rejected SQL: ${rejectedSql.trim()}`,
    `Reviewer feedback: ${feedback.trim()}`,
    "Regenerate a different read-only SQL query for the same request that addresses the reviewer feedback.",
    "Do not repeat the rejected SQL unchanged.",
  ]
    .filter(Boolean)
    .join("\n\n");
}

function RobotAvatarIcon({ speaker }: { speaker: "llm" | "judge" }) {
  return (
    <svg viewBox="0 0 36 36" className={`judge-robot-icon ${speaker}`} aria-hidden="true">
      <path d="M18 5V3" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <circle cx="18" cy="2.6" r="1.6" fill="currentColor" />
      <rect x="9" y="8" width="18" height="12" rx="6" fill="rgba(255,255,255,0.08)" stroke="currentColor" strokeWidth="1.8" />
      <circle cx="14" cy="14" r="1.7" fill="currentColor" />
      <circle cx="22" cy="14" r="1.7" fill="currentColor" />
      <path d="M14 24h8" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M11.5 20.2l-2.8 3M24.5 20.2l2.8 3" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M14.2 20v5.4M21.8 20v5.4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M13 30.2l1.8-3.2M23 30.2l-1.8-3.2" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function JudgeSpeakerAvatar({ speaker }: { speaker: "llm" | "judge" }) {
  return <RobotAvatarIcon speaker={speaker} />;
}

function FailureCallout({ message }: { message: string }) {
  const failureCopy = getFailureCopy(message);

  return (
    <section className="panel error-panel failure-callout-panel">
      <div className="panel-header failure-panel-header">
        <div className="section-heading compact">
          <p className="eyebrow">Run status</p>
          <h2>Execution failed</h2>
        </div>
        <span className="status-pill error">Failed</span>
      </div>
      <p className="failure-panel-copy">{failureCopy.primary}</p>
      <p className="muted failure-panel-subcopy">{failureCopy.secondary}</p>
    </section>
  );
}

function getDataSourceSteps(dataSource: DataSourceState, isPostgresFormOpen: boolean) {
  if (dataSource.status === "updating_mode") {
    return [
      { label: dataSource.configured ? "Datasource connected" : "Execution mode selected", state: "completed" },
      { label: "Switch execution mode", state: "active" },
      { label: "Apply backend env", state: "active" },
      { label: "Refresh agent rules", state: "pending" },
    ];
  }

  if (dataSource.configured) {
    return [
      { label: "Database selected", state: "completed" },
      { label: "Connecting to database", state: "completed" },
      { label: "Connection verified", state: "completed" },
      { label: "Schema discovery ready", state: "completed" },
    ];
  }

  if (dataSource.status === "saving") {
    return [
      { label: "Database selected", state: "completed" },
      { label: "Connecting to database", state: "active" },
      { label: "Connection verified", state: "pending" },
      { label: "Schema discovery ready", state: "pending" },
    ];
  }

  if (dataSource.status === "disconnecting") {
    return [
      { label: "Database selected", state: "completed" },
      { label: "Disconnecting datasource", state: "active" },
      { label: "Connection removed", state: "pending" },
      { label: "Ready for a new source", state: "pending" },
    ];
  }

  if (dataSource.status === "error") {
    return [
      { label: "Database selected", state: isPostgresFormOpen ? "completed" : "active" },
      { label: "Connecting to database", state: "error" },
      { label: "Fix connection URL", state: "active" },
      { label: "Retry validation", state: "pending" },
    ];
  }

  if (isPostgresFormOpen) {
    return [
      { label: "Database selected", state: "active" },
      { label: "Paste DB URL", state: "pending" },
      { label: "Validate connection", state: "pending" },
      { label: "Start querying", state: "pending" },
    ];
  }

  return [
    { label: "Choose a database", state: "active" },
    { label: "Enter DB URL", state: "pending" },
    { label: "Validate connection", state: "pending" },
    { label: "Start querying", state: "pending" },
  ];
}

function getDataSourceProgressValue(dataSource: DataSourceState, isPostgresFormOpen: boolean) {
  if (dataSource.status === "updating_mode") {
    return dataSource.configured ? 88 : 26;
  }

  if (dataSource.configured) {
    return 100;
  }

  if (dataSource.status === "saving") {
    return 62;
  }

  if (dataSource.status === "disconnecting") {
    return 45;
  }

  if (dataSource.status === "error") {
    return 28;
  }

  if (isPostgresFormOpen) {
    return 14;
  }

  return 6;
}

function getExecutionModeLabel(mode: DataSourceState["executionMode"]) {
  return mode === "pro" ? "Environment: Pro" : "Environment: Non-Pro";
}

function getAccessModeLabel(mode: DataSourceState["accessMode"]) {
  return mode === "read_only" ? "Read only" : "Write enabled";
}

function RaceCarIcon() {
  return (
    <svg viewBox="0 0 84 34" className="progress-racer-icon" aria-hidden="true">
      <path d="M17 22h6l7-8h20l8 4h8c4 0 7 2.7 7 6v2H12v-2c0-1.2.4-2.2 1.2-3l3.8-3.2Z" fill="currentColor" opacity="0.98" />
      <path d="M33 14l5-6h13l6 6H33Z" fill="rgba(255,255,255,0.18)" />
      <circle cx="24" cy="26" r="5" fill="#091224" />
      <circle cx="24" cy="26" r="2.3" fill="#8ef3ff" />
      <circle cx="58" cy="26" r="5" fill="#091224" />
      <circle cx="58" cy="26" r="2.3" fill="#8ef3ff" />
    </svg>
  );
}

function ThemeToggleButton({ theme, onToggle }: { theme: ThemeMode; onToggle: () => void }) {
  const nextLabel = theme === "dark" ? "Light mode" : "Dark mode";

  return (
    <button type="button" className="ghost-button theme-toggle" onClick={onToggle} aria-label={`Switch to ${nextLabel}`} title={nextLabel}>
      <span className="theme-toggle-icon" aria-hidden="true">
        {theme === "dark" ? (
          <svg viewBox="0 0 24 24" className="theme-icon-svg">
            <circle cx="12" cy="12" r="4.2" fill="currentColor" />
            <path d="M12 2.5v2.6M12 18.9v2.6M21.5 12h-2.6M5.1 12H2.5M18.8 5.2l-1.8 1.8M7 17l-1.8 1.8M18.8 18.8 17 17M7 7 5.2 5.2" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" className="theme-icon-svg">
            <path d="M14.7 3.3a8.8 8.8 0 1 0 6 14.3 8.9 8.9 0 0 1-5.7 2A8.8 8.8 0 0 1 10 4.7c1.4-.7 3-.9 4.7-1.4Z" fill="currentColor" />
          </svg>
        )}
      </span>
    </button>
  );
}

function PostgresIcon() {
  return (
    <svg viewBox="0 0 64 64" aria-hidden="true" className="datasource-icon">
      <ellipse cx="32" cy="14" rx="18" ry="8" fill="currentColor" opacity="0.2" />
      <path d="M14 14v20c0 4.4 8.1 8 18 8s18-3.6 18-8V14" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M14 24c0 4.4 8.1 8 18 8s18-3.6 18-8" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
      <path d="M14 34c0 4.4 8.1 8 18 8s18-3.6 18-8" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
    </svg>
  );
}

function SqlServerIcon() {
  return (
    <svg viewBox="0 0 64 64" aria-hidden="true" className="datasource-icon sqlserver-icon">
      <path d="M14 20c0-5.5 8-10 18-10 7.2 0 13.4 2.4 16.4 5.9 1 1.2.7 3-0.7 3.8-3.8 2.2-9.5 3.6-15.7 3.6-10 0-18-4.5-18-10.3Z" fill="currentColor" opacity="0.24" />
      <path d="M18 20c4.5 2.2 8.7 3.3 12.7 3.3 6.9 0 12.9-3.4 17.6-8.3" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
      <path d="M46 18c-3.8 6.4-4.2 12.2-1.2 17.3 2.7 4.7 2.3 10-1.4 14.7" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M28 26c6.4 4.2 10.1 9.3 11.1 15.3" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
      <path d="M18 38c5.3-1.7 10.4-1.3 15.3 1.2" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
    </svg>
  );
}

function MongoIcon() {
  return (
    <svg viewBox="0 0 64 64" aria-hidden="true" className="datasource-icon mongo-icon">
      <path d="M33 10c1.4 6.3 8.5 11 8.5 23.3 0 8.7-3.4 15.5-9.5 20.7-6.1-5.2-9.5-12-9.5-20.7C22.5 21 29.4 16.2 31 10h2Z" fill="currentColor" opacity="0.18" />
      <path d="M32 10c4.8 5.7 7.9 13.8 7.9 23.3 0 7.8-2.8 14.8-7.9 20.7-5.1-5.9-7.9-12.9-7.9-20.7C24.1 23.8 27.2 15.7 32 10Z" fill="none" stroke="currentColor" strokeWidth="4" strokeLinejoin="round" />
      <path d="M32 16v34" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
    </svg>
  );
}

function StatCard({ label, value, tone }: { label: string; value: string; tone?: "teal" | "amber" | "violet" }) {
  return (
    <div className={`stat-card ${tone ?? "teal"}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function TodoPanel({ todos, isLoading }: { todos: TodoItem[]; isLoading: boolean }) {
  const activeTodoRef = useRef<HTMLLIElement | null>(null);
  const activeTodoKey = todos.findIndex((todo) => todo.status === "in_progress");

  useEffect(() => {
    if (activeTodoKey < 0 || !activeTodoRef.current) {
      return;
    }

    activeTodoRef.current.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
      inline: "nearest",
    });
  }, [activeTodoKey]);

  if (todos.length === 0 && !isLoading) {
    return (
      <section className="panel accent-panel elevated-panel todo-stage-panel">
        <div className="section-heading">
          <p className="eyebrow">DeepAgent progress</p>
          <h2>Agent progress</h2>
        </div>
        <p className="muted">Submit a plain-English query to watch the agent plan schema discovery, SQL generation, and policy-aware execution.</p>
      </section>
    );
  }

  const completed = todos.filter((todo) => todo.status === "completed").length;
  const percentage = todos.length ? Math.round((completed / todos.length) * 100) : 0;
  return (
    <section className="panel accent-panel elevated-panel todo-stage-panel">
      <div className="panel-header">
        <div className="section-heading compact">
          <p className="eyebrow">DeepAgent progress</p>
          <h2>Agent progress</h2>
        </div>
        <strong>{percentage}%</strong>
      </div>
      <div className="progress-track cinematic-track race-progress-track" aria-hidden="true">
        <div className="progress-fill" style={{ width: `${percentage}%` }} />
        <div className="progress-racer" style={{ left: `clamp(18px, calc(${percentage}% - 24px), calc(100% - 28px))` }}>
          <span className="progress-racer-smoke smoke-a" />
          <span className="progress-racer-smoke smoke-b" />
          <span className="progress-racer-glow" />
          <RaceCarIcon />
        </div>
        <div className="progress-finish-flag">
          <span />
          <span />
        </div>
      </div>
      {todos.length === 0 && isLoading ? <p className="muted shimmer-line">Creating a plan...</p> : null}
      <ul className="todo-list deluxe-todo-list">
        {todos.map((todo, index) => {
          const style = getStatusConfig(todo.status);
          const isActive = todo.status === "in_progress";
          const showsConnector = index < todos.length - 1;
          const connectorStateClass = todo.status === "completed" ? "passed" : isActive ? "is-live" : "";
          return (
            <li key={`${normalizeTodoLabel(todo)}-${index}`} className="todo-shell" ref={isActive ? activeTodoRef : null}>
              <article className={`${style.className} todo-card ${isActive ? "is-focused" : ""}`}>
                {isActive ? <span className="todo-drop-marker" aria-hidden="true" /> : null}
                {isActive ? <span className="todo-drop-marker right-edge" aria-hidden="true" /> : null}
                {showsConnector ? (
                  <span className={`todo-connector ${connectorStateClass}`.trim()} aria-hidden="true">
                    <span className="todo-connector-line" />
                    <span className="todo-connector-rungs" />
                    <span className="todo-connector-check">✓</span>
                  </span>
                ) : null}
                {showsConnector ? (
                  <span className={`todo-connector right-edge ${connectorStateClass}`.trim()} aria-hidden="true">
                    <span className="todo-connector-line" />
                    <span className="todo-connector-rungs" />
                    <span className="todo-connector-check">✓</span>
                  </span>
                ) : null}
                {isActive ? (
                  <span className="workflow-agent" aria-hidden="true">
                    <WorkflowAgentIcon />
                    <span className="workflow-agent-glow" />
                  </span>
                ) : null}
                {isActive ? (
                  <span className="workflow-agent right-edge is-echo" aria-hidden="true">
                    <WorkflowAgentIcon />
                    <span className="workflow-agent-glow" />
                  </span>
                ) : null}
                <span className="todo-accent-rail" aria-hidden="true" />
                <span className="todo-icon-wrap todo-icon-panel">
                  {todo.status === "in_progress" ? <span className="todo-spinner" aria-hidden="true" /> : <span className="todo-icon">{style.icon}</span>}
                </span>
                <div className="todo-copy">
                  <strong>{normalizeTodoLabel(todo)}</strong>
                  {todo.description ? <span className="muted todo-support-copy">{todo.description}</span> : null}
                </div>
                <span className="todo-state-tag">{style.caption}</span>
              </article>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function GeneratedSqlPanel({ sql, status, rowCount, isRetrying }: { sql: string; status: StreamState["status"]; rowCount: number; isRetrying: boolean }) {
  const [typedSql, setTypedSql] = useState("");
  const [copyState, setCopyState] = useState<"idle" | "copied" | "error">("idle");
  const statementCount = getSqlStatementCount(sql);
  const statementChunks = useMemo(() => splitSqlStatements(sql), [sql]);
  const typedStatementChunks = useMemo(() => getTypedStatementChunks(sql, typedSql), [sql, typedSql]);

  useEffect(() => {
    if (!sql) {
      setTypedSql("");
      return;
    }

    setTypedSql("");
    let index = 0;
    let cancelled = false;

    const typeNextCharacter = () => {
      if (cancelled) {
        return;
      }

      index += 1;
      setTypedSql(sql.slice(0, index));

      if (index >= sql.length) {
        return;
      }

      const currentCharacter = sql[index - 1] ?? "";
      const nextDelay = currentCharacter === "\n" ? 110 : /[(),;]/.test(currentCharacter) ? 58 : currentCharacter === " " ? 18 : 28;
      window.setTimeout(typeNextCharacter, nextDelay);
    };

    const startTimer = window.setTimeout(typeNextCharacter, 120);

    return () => {
      cancelled = true;
      window.clearTimeout(startTimer);
    };
  }, [sql]);

  const terminalText = typedSql || (status === "running" ? "Preparing SQL..." : "SQL will appear here once generated.");

  const handleCopySql = async () => {
    if (!sql.trim()) {
      return;
    }

    try {
      await navigator.clipboard.writeText(sql);
      setCopyState("copied");
      window.setTimeout(() => setCopyState("idle"), 1600);
    } catch {
      setCopyState("error");
      window.setTimeout(() => setCopyState("idle"), 1600);
    }
  };

  return (
    <section className={`panel glass-panel terminal-panel ${sql ? "terminal-ready" : ""}`}>
      <div className="panel-header terminal-header">
        <div className="section-heading compact">
          <p className="eyebrow">SQL execution</p>
          <h2>Generated SQL</h2>
        </div>
        <div className="terminal-action-cluster">
          {statementCount > 1 ? <span className="sql-meta-badge">{statementCount} statements</span> : null}
          {isRetrying ? <span className="sql-meta-badge retrying-badge">Retrying...</span> : null}
          <button type="button" className={`ghost-button copy-sql-button ${copyState}`} onClick={() => void handleCopySql()} disabled={!sql.trim()}>
            {copyState === "copied" ? "Copied" : copyState === "error" ? "Retry copy" : "Copy query"}
          </button>
        </div>
      </div>
      <div className="terminal-shell">
        <div className="terminal-toolbar" aria-hidden="true">
          <span className="terminal-dot red" />
          <span className="terminal-dot amber" />
          <span className="terminal-dot green" />
          <span className="terminal-tab" />
        </div>
        <div className="terminal-stage">
          {statementChunks.length > 1 ? (
            <div className="statement-stack">
              {statementChunks.map((statement, index) => {
                const visibleSql = typedStatementChunks[index] ?? "";
                const hasStarted = visibleSql.length > 0;
                const hasCompleted = visibleSql.length >= statement.length;
                return (
                  <div key={`statement-${index + 1}`} className="statement-block">
                    <div className="statement-block-header">
                      <span className="statement-label">Statement {index + 1}</span>
                      {hasCompleted ? <span className="statement-state ready">Ready</span> : hasStarted ? <span className="statement-state typing">Typing</span> : <span className="statement-state waiting">Queued</span>}
                    </div>
                    <div className="terminal-line statement-terminal-line">
                      <span className="terminal-prompt">sql&gt;</span>
                      <pre className="code-block terminal-code statement-code">
                        {renderHighlightedSql(visibleSql || (status === "running" ? "Awaiting statement..." : statement.trim()))}
                      </pre>
                      {hasStarted && !hasCompleted ? <span className="terminal-caret" aria-hidden="true" /> : null}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="terminal-line">
              <span className="terminal-prompt">sql&gt;</span>
              <pre className="code-block terminal-code">{sql ? renderHighlightedSql(terminalText) : terminalText}</pre>
              {sql && typedSql.length < sql.length ? <span className="terminal-caret" aria-hidden="true" /> : null}
            </div>
          )}
          <div className={`terminal-status-row ${rowCount > 0 ? "result-ready" : ""}`}>
            <span>{status === "running" ? "Executing query..." : rowCount > 0 ? `${rowCount} rows ready` : "Awaiting execution."}</span>
            <span className="terminal-status-pulse" aria-hidden="true" />
          </div>
        </div>
      </div>
    </section>
  );
}

function JudgeTranscriptMessage({ entry, isLatest }: { entry: JudgeTranscriptEntry; isLatest: boolean }) {
  const [typedMessage, setTypedMessage] = useState(isLatest ? "" : entry.message);

  useEffect(() => {
    if (!isLatest) {
      setTypedMessage(entry.message);
      return;
    }

    setTypedMessage("");
    let index = 0;
    let cancelled = false;

    const typeNextCharacter = () => {
      if (cancelled) {
        return;
      }

      index += 1;
      setTypedMessage(entry.message.slice(0, index));

      if (index >= entry.message.length) {
        return;
      }

      const currentCharacter = entry.message[index - 1] ?? "";
      const nextDelay = currentCharacter === " " ? 18 : /[.,;:]/.test(currentCharacter) ? 72 : currentCharacter === "\n" ? 96 : 22;
      window.setTimeout(typeNextCharacter, nextDelay);
    };

    const startTimer = window.setTimeout(typeNextCharacter, 120);

    return () => {
      cancelled = true;
      window.clearTimeout(startTimer);
    };
  }, [entry.id, entry.message, isLatest]);

  const visibleMessage = isLatest ? typedMessage : entry.message;
  const isTyping = isLatest && typedMessage.length < entry.message.length;

  return (
    <div className="judge-entry-bubble">
      <div className="judge-entry-bubble-content">
        <p>{visibleMessage}</p>
        {isTyping ? <span className="terminal-caret judge-entry-caret" aria-hidden="true" /> : null}
      </div>
      <span className="judge-entry-time">{entry.timestamp}</span>
    </div>
  );
}

function ApprovalModal({
  approval,
  isSubmitting,
  isRejectFlowOpen,
  feedback,
  onFeedbackChange,
  onApprove,
  onBeginReject,
  onCancelReject,
  onConfirmReject,
}: {
  approval: PendingApproval;
  isSubmitting: boolean;
  isRejectFlowOpen: boolean;
  feedback: string;
  onFeedbackChange: (value: string) => void;
  onApprove: () => void;
  onBeginReject: () => void;
  onCancelReject: () => void;
  onConfirmReject: () => void;
}) {
  return (
    <div className="datasource-modal-backdrop approval-modal-backdrop" role="presentation">
      <section className="panel glass-panel datasource-modal approval-modal" role="dialog" aria-modal="true" aria-labelledby="approval-modal-title">
        <div className="panel-header datasource-modal-header">
          <div className="section-heading compact">
            <p className="eyebrow">Human in the loop</p>
            <h2 id="approval-modal-title">Approve SQL execution in Pro mode</h2>
          </div>
          <span className="sql-meta-badge judge-status-badge awaiting_approval">Awaiting approval</span>
        </div>

        <div className="approval-modal-grid">
          <div className="approval-modal-copy">
            <p className="muted approval-modal-intro">
              Judge approval is complete. Execution is paused until a human reviewer approves or rejects this SQL.
            </p>
            <div className="approval-summary-card">
              <div className="approval-summary-row">
                <span>Execution mode</span>
                <strong>{approval.executionMode === "pro" ? "Pro" : "Non-Pro"}</strong>
              </div>
              <div className="approval-summary-row">
                <span>Judge commentary</span>
                <strong>{approval.commentary}</strong>
              </div>
            </div>
            {approval.reasons.length > 0 ? (
              <div className="approval-reasons-panel">
                <p className="eyebrow">Judge reasons</p>
                <ul className="approval-reason-list">
                  {approval.reasons.map((reason, index) => (
                    <li key={`${reason}-${index}`}>{reason}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            <div className="approval-sql-preview">
              <p className="eyebrow">Pending SQL</p>
              <pre className="code-block terminal-code approval-sql-code">{renderHighlightedSql(approval.sql)}</pre>
            </div>
          </div>

          <div className="approval-action-panel">
            <div className="approval-avatar-stage">
              <span className="judge-entry-avatar approval-avatar" aria-hidden="true">
                <JudgeSpeakerAvatar speaker="judge" />
              </span>
              <div>
                <strong>Human approval required</strong>
                <p className="muted">For this PoC, the reviewer confirms the query inside the same UI. Later this can move to a separate approval endpoint or workflow.</p>
              </div>
            </div>
            {isRejectFlowOpen ? (
              <label className="approval-feedback-field">
                <span>Feedback for regeneration</span>
                <textarea
                  rows={4}
                  value={feedback}
                  onChange={(event) => onFeedbackChange(event.target.value)}
                  placeholder="Tell the agent what should change in the next SQL query"
                  disabled={isSubmitting}
                />
              </label>
            ) : null}
            <div className="approval-button-stack">
              {isRejectFlowOpen ? (
                <>
                  <button
                    type="button"
                    className="primary-button cinematic-button"
                    onClick={onConfirmReject}
                    disabled={isSubmitting || !feedback.trim()}
                  >
                    {isSubmitting ? "Processing..." : "Disapprove and regenerate"}
                  </button>
                  <button type="button" className="ghost-button luminous-button" onClick={onCancelReject} disabled={isSubmitting}>
                    Cancel disapprove
                  </button>
                </>
              ) : (
                <>
                  <button type="button" className="primary-button cinematic-button" onClick={onApprove} disabled={isSubmitting}>
                    {isSubmitting ? "Processing..." : "Approve and execute"}
                  </button>
                  <button type="button" className="ghost-button disconnect-button" onClick={onBeginReject} disabled={isSubmitting}>
                    Disapprove SQL
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function JudgeIdleDots() {
  return (
    <span className="judge-idle-dots" aria-label="Judge terminal idle">
      <span />
      <span />
      <span />
    </span>
  );
}

function JudgeTerminalPanel({
  transcript,
  judgeStatus,
  commentary,
}: {
  transcript: JudgeTranscriptEntry[];
  judgeStatus: StreamState["judgeStatus"];
  commentary: string;
}) {
  const transcriptRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const container = transcriptRef.current;
    if (!container) {
      return;
    }

    container.scrollTo({
      top: container.scrollHeight,
      behavior: transcript.length > 1 ? "smooth" : "auto",
    });
  }, [transcript.length, judgeStatus]);

  const statusLabel =
    judgeStatus === "reviewing"
      ? "Reviewing"
      : judgeStatus === "awaiting_approval"
        ? "Awaiting human approval"
      : judgeStatus === "approved"
        ? "Approved"
        : judgeStatus === "rejected"
          ? "Rejected"
          : "Idle";

  const placeholderCopy =
    judgeStatus === "reviewing"
      ? "Judge is reviewing the generated SQL..."
      : commentary || "Judge review events will appear here once SQL is generated.";

  return (
    <section className="panel glass-panel judge-terminal-panel">
      <div className="panel-header terminal-header judge-terminal-header">
        <div className="section-heading compact">
          <p className="eyebrow">Judge review</p>
          <h2>LLM as a JUDGE Terminal</h2>
        </div>
        <div className="terminal-action-cluster">
          <span className={`sql-meta-badge judge-status-badge ${judgeStatus}`}>{statusLabel}</span>
        </div>
      </div>
      <div className="terminal-shell judge-terminal-shell">
        <div className="terminal-toolbar" aria-hidden="true">
          <span className="terminal-dot red" />
          <span className="terminal-dot amber" />
          <span className="terminal-dot green" />
          <span className="terminal-tab" />
        </div>
        <div className="terminal-stage judge-terminal-stage">
          {transcript.length > 0 ? (
            <div className="judge-transcript" ref={transcriptRef}>
              {transcript.map((entry, index) => (
                <div key={entry.id} className={`judge-entry ${entry.side} ${entry.tone}`} style={{ animationDelay: `${Math.min(index * 70, 420)}ms` }}>
                  <div className="judge-entry-rail">
                    <span className="judge-entry-avatar" aria-hidden="true">
                      <JudgeSpeakerAvatar speaker={entry.speaker} />
                    </span>
                    <div className="judge-entry-stack">
                      <span className="judge-entry-label">{getJudgeSpeakerMeta(entry.speaker).label}</span>
                      <JudgeTranscriptMessage entry={entry} isLatest={index === transcript.length - 1} />
                    </div>
                  </div>
                </div>
              ))}
              {judgeStatus === "reviewing" ? (
                <div className="judge-entry right judge-typing-indicator">
                  <div className="judge-entry-rail">
                    <span className="judge-entry-avatar" aria-hidden="true">
                      <JudgeSpeakerAvatar speaker="judge" />
                    </span>
                    <div className="judge-entry-stack">
                      <span className="judge-entry-label">Judge</span>
                      <div className="judge-entry-bubble judge-typing-bubble">
                        <ThinkingDots />
                      </div>
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          ) : (
            <div className="judge-placeholder-stage">
              <JudgeIdleDots />
              <div className="judge-placeholder-message">
                <span className="judge-entry-avatar judge-placeholder-avatar" aria-hidden="true">
                  <JudgeSpeakerAvatar speaker="judge" />
                </span>
                <p className="judge-placeholder-copy">{placeholderCopy}</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function SummaryPanel({ summary, status, statementCount }: { summary: string; status: StreamState["status"]; statementCount: number }) {
  const [typedSummary, setTypedSummary] = useState("");

  useEffect(() => {
    if (!summary) {
      setTypedSummary("");
      return;
    }

    setTypedSummary("");
    let index = 0;
    let cancelled = false;

    const typeNextCharacter = () => {
      if (cancelled) {
        return;
      }

      index += 1;
      setTypedSummary(summary.slice(0, index));

      if (index >= summary.length) {
        return;
      }

      const currentCharacter = summary[index - 1] ?? "";
      const nextDelay = currentCharacter === "." || currentCharacter === "," ? 90 : currentCharacter === " " ? 20 : currentCharacter === "\n" ? 120 : 34;
      window.setTimeout(typeNextCharacter, nextDelay);
    };

    const startTimer = window.setTimeout(typeNextCharacter, 150);

    return () => {
      cancelled = true;
      window.clearTimeout(startTimer);
    };
  }, [summary]);

  const displayText = typedSummary || (status === "running" ? "" : "Waiting for the final response summary...");
  const isTyping = Boolean(summary) && typedSummary.length < summary.length;
  const showThinkingDots = status === "running" && !summary;
  const hasStatementInsights = statementCount > 1;
  const statementInsightChunks = useMemo(() => buildStatementInsights(summary, statementCount), [summary, statementCount]);
  const typedInsightChunks = useMemo(() => buildStatementInsights(typedSummary, statementCount), [typedSummary, statementCount]);

  return (
    <section className="panel glass-panel summary-panel summary-terminal-panel">
      <div className="section-heading compact">
        <p className="eyebrow">Dashboard summary</p>
        <h2>Summary</h2>
      </div>
      <div className="summary-shell">
        <div className="summary-shell-header" aria-hidden="true">
          <span className="summary-shell-dot" />
          <span className="summary-shell-dot" />
          <span className="summary-shell-dot" />
          <span className="summary-shell-label">{hasStatementInsights ? "Statement insights" : "Insight feed"}</span>
        </div>
        <div className="summary-stage">
          {hasStatementInsights ? (
            <div className="summary-statement-stack">
              {statementInsightChunks.map((insight, index) => {
                const visibleInsight = typedInsightChunks[index] ?? "";
                const hasStarted = visibleInsight.length > 0;
                const hasCompleted = Boolean(insight) && visibleInsight.length >= insight.length;
                const content = visibleInsight || (showThinkingDots ? "" : status === "running" ? "Awaiting insight..." : insight || "Waiting for the final response summary...");

                return (
                  <div key={`summary-statement-${index + 1}`} className="summary-statement-card">
                    <div className="summary-statement-header">
                      <span className="statement-label">Statement {index + 1}</span>
                      {hasCompleted ? <span className="statement-state ready">Ready</span> : hasStarted ? <span className="statement-state typing">Typing</span> : <span className="statement-state waiting">Queued</span>}
                    </div>
                    <div className="summary-line statement-summary-line">
                      <span className="summary-prompt">insight&gt;</span>
                      <div className="summary-copy-wrap statement-summary-copy-wrap">
                        {!hasStarted && showThinkingDots ? <ThinkingDots /> : <p className="summary-text summary-typed-text">{content}</p>}
                        {hasStarted && !hasCompleted ? <span className="summary-caret" aria-hidden="true" /> : null}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="summary-line">
              <span className="summary-prompt">insight&gt;</span>
              <div className="summary-copy-wrap">
                {showThinkingDots ? <ThinkingDots /> : <p className="summary-text summary-typed-text">{displayText}</p>}
                {isTyping ? <span className="summary-caret" aria-hidden="true" /> : null}
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function ResultTable({ rows, statementCount, sql }: { rows: Array<Record<string, unknown>>; statementCount: number; sql: string }) {
  const statementGroups = useMemo(() => buildStatementGroups(rows, sql), [rows, sql]);
  const [copyState, setCopyState] = useState<Record<string, "idle" | "copied" | "error">>({});
  const columns = useMemo(() => {
    const names = new Set<string>();
    rows.forEach((row) => Object.keys(row).forEach((key) => names.add(key)));
    return Array.from(names);
  }, [rows]);

  const handleCopyGroup = async (groupKey: string, groupRows: Array<Record<string, unknown>>, groupColumns: string[]) => {
    const payload = serializeResultRows(groupRows, groupColumns);
    if (!payload) {
      return;
    }

    try {
      await navigator.clipboard.writeText(payload);
      setCopyState((current) => ({ ...current, [groupKey]: "copied" }));
    } catch {
      setCopyState((current) => ({ ...current, [groupKey]: "error" }));
    }

    window.setTimeout(() => {
      setCopyState((current) => ({ ...current, [groupKey]: "idle" }));
    }, 1600);
  };

  if (rows.length === 0 || columns.length === 0) {
    return (
      <section className="panel glass-panel result-panel result-empty">
        <div className="section-heading compact">
          <p className="eyebrow">Query result</p>
          <h2>Query result</h2>
        </div>
        <p className="muted">Rows will render here when the query finishes.</p>
      </section>
    );
  }

  return (
    <section className="panel glass-panel result-panel result-ready">
      <div className="panel-header">
        <div className="section-heading compact">
          <p className="eyebrow">Query result</p>
          <h2>Query result</h2>
        </div>
        <strong>{rows.length} rows</strong>
      </div>
      {statementCount > 1 ? <p className="muted result-helper-copy">Multiple SQL statements were generated. When the backend returns grouped result sets, they will render in separate sections below. Until then, any combined response is shown as one grouped block.</p> : null}
      <div className="result-groups">
        {statementGroups.map((group) => {
          const groupColumns = Array.from(new Set(group.rows.flatMap((row) => Object.keys(row))));
          const groupCopyState = copyState[group.key] ?? "idle";
          const combinedDatasets = group.isCombined ? buildCombinedDatasets(group.rows) : [];
          return (
            <section key={group.key} className="result-group-card">
              <div className="panel-header result-group-header">
                <div>
                  <strong>{group.label}</strong>
                  {group.sql ? <p className="muted result-group-sql">{group.sql}</p> : null}
                </div>
                <button
                  type="button"
                  className={`ghost-button copy-sql-button copy-result-button ${groupCopyState}`}
                  onClick={() => void handleCopyGroup(group.key, group.rows, groupColumns)}
                  disabled={group.rows.length === 0 || groupColumns.length === 0}
                >
                  {groupCopyState === "copied" ? "Copied" : groupCopyState === "error" ? "Retry copy" : "Copy result"}
                </button>
              </div>
              {group.isCombined ? <p className="muted result-group-note">Current backend payload is flattened across statements. This card groups that combined response until per-statement rows are emitted.</p> : null}
              {combinedDatasets.length > 0 ? (
                <div className="result-dataset-grid">
                  {combinedDatasets.map((dataset) => (
                    <section key={`${group.key}-${dataset.key}`} className="result-dataset-card">
                      <div className="panel-header result-dataset-header">
                        <strong>{dataset.label}</strong>
                        <span className="sql-meta-badge">{dataset.rows.length} rows</span>
                      </div>
                      <div className="table-wrap futuristic-table-wrap">
                        <table>
                          <thead>
                            <tr>
                              {dataset.columns.map((column) => (
                                <th key={`${dataset.key}-${column}`}>{column}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {dataset.rows.map((row, rowIndex) => (
                              <tr key={`${dataset.key}-${rowIndex}`}>
                                {dataset.columns.map((column) => (
                                  <td key={`${dataset.key}-${rowIndex}-${column}`}>{renderResultCell(row[column])}</td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </section>
                  ))}
                </div>
              ) : (
                <div className="table-wrap futuristic-table-wrap">
                  <table>
                    <thead>
                      <tr>
                        {groupColumns.map((column) => (
                          <th key={column}>{column}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {group.rows.map((row, rowIndex) => (
                        <tr key={`${group.key}-${rowIndex}`}>
                          {groupColumns.map((column) => (
                            <td key={`${group.key}-${rowIndex}-${column}`}>{renderResultCell(row[column])}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          );
        })}
      </div>
    </section>
  );
}

function DataSourcePanel({
  dataSource,
  isPickerOpen,
  isPostgresFormOpen,
  connectionUrl,
  onOpenPicker,
  onClosePicker,
  onChoosePostgres,
  onConnectionUrlChange,
  onSubmit,
  onDisconnect,
  onExecutionModeChange,
}: {
  dataSource: DataSourceState;
  isPickerOpen: boolean;
  isPostgresFormOpen: boolean;
  connectionUrl: string;
  onOpenPicker: () => void;
  onClosePicker: () => void;
  onChoosePostgres: () => void;
  onConnectionUrlChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onDisconnect: () => Promise<void>;
  onExecutionModeChange: (mode: DataSourceState["executionMode"]) => Promise<void>;
}) {
  const steps = getDataSourceSteps(dataSource, isPostgresFormOpen);
  const progressValue = getDataSourceProgressValue(dataSource, isPostgresFormOpen);
  const isModeUpdating = dataSource.status === "updating_mode";
  const isBusy = dataSource.status === "saving" || dataSource.status === "disconnecting" || isModeUpdating;
  const statusTone = dataSource.configured && !isModeUpdating ? "success" : dataSource.status === "error" ? "error" : dataSource.status === "saving" || dataSource.status === "disconnecting" || isModeUpdating ? "running" : "idle";
  const statusLabel = dataSource.configured && !isModeUpdating ? "connected" : dataSource.status === "saving" ? "connecting" : dataSource.status === "disconnecting" ? "disconnecting" : dataSource.status === "updating_mode" ? "switching mode" : dataSource.status;
  const showInlineFormFeedback = isPostgresFormOpen && (dataSource.status === "error" || dataSource.status === "saving");

  return (
    <section className="panel datasource-panel hero-panel">
      <div className="panel-header datasource-header">
        <div className="section-heading compact">
          <p className="eyebrow">Datasource setup</p>
          <h2>Connect data source</h2>
        </div>
        <div className="button-row datasource-actions">
          <button type="button" className="ghost-button luminous-button" onClick={onOpenPicker}>
            {dataSource.configured ? "Change data source" : "Connect data source"}
          </button>
          {dataSource.configured ? (
            <button type="button" className="ghost-button disconnect-button" onClick={() => void onDisconnect()} disabled={isBusy}>
              {dataSource.status === "disconnecting" ? "Disconnecting..." : "Disconnect source"}
            </button>
          ) : null}
        </div>
      </div>

      <div className="datasource-status-shell">
        <div className="datasource-status-row">
          <span className={`status-pill ${statusTone}`}>
            {statusLabel}
          </span>
          <div>
            <strong>{dataSource.provider ? dataSource.provider.toUpperCase() : "No provider selected"}</strong>
            <p className="muted">{dataSource.databaseLabel || dataSource.message}</p>
          </div>
          <span className={`datasource-light ${statusTone}`} aria-hidden="true" />
        </div>

        <div className="progress-track cinematic-track datasource-progress-track" aria-label="Datasource connection progress">
          <div className={`progress-fill datasource-progress-fill ${statusTone}`} style={{ width: `${progressValue}%` }} />
        </div>

        <div className={`datasource-feedback ${statusTone}`} role="status" aria-live="polite">
          {dataSource.message}
        </div>

        <div className="datasource-mode-shell">
          <div>
            <p className="eyebrow">Execution mode</p>
            <h3 className="datasource-mode-title">Backend safety mode</h3>
            <p className="muted datasource-mode-copy">
              {dataSource.executionMode === "pro"
                ? "Pro requires human approval before read-only SQL execution."
                : "Non-Pro automatically approves queries; SQL execution remains read-only."}
            </p>
          </div>
          <div className="datasource-mode-toggle" role="group" aria-label="Execution mode toggle">
            <button
              type="button"
              className={`datasource-mode-button ${dataSource.executionMode === "pro" ? "active" : ""}`}
              onClick={() => void onExecutionModeChange("pro")}
              disabled={isBusy || dataSource.executionMode === "pro"}
            >
              <strong>Pro</strong>
              <span>Read only</span>
            </button>
            <button
              type="button"
              className={`datasource-mode-button ${dataSource.executionMode === "non_pro" ? "active non-pro" : "non-pro"}`}
              onClick={() => void onExecutionModeChange("non_pro")}
              disabled={isBusy || dataSource.executionMode === "non_pro"}
            >
              <strong>Non-Pro</strong>
              <span>Auto approve</span>
            </button>
          </div>
        </div>

        <div className="datasource-steps">
          {steps.map((step) => (
            <div key={step.label} className={`datasource-step ${step.state}`}>
              <span className="datasource-step-dot" />
              <span>{step.label}</span>
            </div>
          ))}
        </div>
      </div>

      {isPickerOpen ? (
        <div className="datasource-modal-backdrop" onClick={onClosePicker}>
          <div className="datasource-modal panel" onClick={(event) => event.stopPropagation()}>
            <div className="panel-header datasource-modal-header">
              <div className="section-heading compact">
                <p className="eyebrow">Datasource setup</p>
                <h2>Select and connect a datasource</h2>
              </div>
              <button type="button" className="ghost-button modal-close-button" onClick={onClosePicker} aria-label="Close datasource setup" title="Close datasource setup">
                ×
              </button>
            </div>

            <div className="datasource-flow modal-flow">
              <div className="datasource-grid modal-grid">
                <button type="button" className={`datasource-option ${isPostgresFormOpen ? "selected" : ""}`} onClick={onChoosePostgres}>
                  <PostgresIcon />
                  <span>
                    <strong>PostgreSQL</strong>
                    <span className="muted">Validate the DB URL, then connect and close this setup panel.</span>
                  </span>
                </button>

                <div className="datasource-option coming-soon" aria-disabled="true">
                  <SqlServerIcon />
                  <span>
                    <strong>
                      Microsoft SQL Server
                      <small className="coming-soon-badge">Coming soon</small>
                    </strong>
                    <span className="muted">UI card ready. Connection flow can be added next.</span>
                  </span>
                </div>

                <div className="datasource-option coming-soon" aria-disabled="true">
                  <MongoIcon />
                  <span>
                    <strong>
                      MongoDB
                      <small className="coming-soon-badge">Coming soon</small>
                    </strong>
                    <span className="muted">UI card ready. Connection flow can be added next.</span>
                  </span>
                </div>
              </div>

              {isPostgresFormOpen ? (
                <form className="datasource-form datasource-modal-form" onSubmit={onSubmit}>
                  <div className="panel-header">
                    <div>
                      <h3>Connect PostgreSQL</h3>
                      <p className="muted">Enter the Database Connection URL.</p>
                    </div>
                  </div>
                  <label>
                    Connection URL
                    <input
                      type="password"
                      value={connectionUrl}
                      onChange={(event) => onConnectionUrlChange(event.target.value)}
                      placeholder="postgresql://username:password@host:5432/database"
                    />
                  </label>
                  {showInlineFormFeedback ? (
                    <div className={`datasource-inline-feedback ${statusTone}`} role="status" aria-live="polite">
                      {dataSource.message}
                    </div>
                  ) : null}
                  <div className="button-row">
                    <button type="submit" className="primary-button cinematic-button" disabled={isBusy}>
                      {dataSource.status === "saving" ? "Connecting..." : "Connect PostgreSQL"}
                    </button>
                  </div>
                </form>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function App() {
  const [theme, setTheme] = useState<ThemeMode>(getInitialTheme);
  const [contextId, setContextId] = useState(createContextId);
  const [humanQuery, setHumanQuery] = useState("");
  const [streamState, setStreamState] = useState<StreamState>(initialState);
  const [contextHistory, setContextHistory] = useState<ContextHistoryEntry[]>(loadContextHistory);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [dataSource, setDataSource] = useState<DataSourceState>(initialDataSourceState);
  const [isDataSourcePickerOpen, setIsDataSourcePickerOpen] = useState(false);
  const [isPostgresFormOpen, setIsPostgresFormOpen] = useState(false);
  const [connectionUrl, setConnectionUrl] = useState("");
  const [pendingApproval, setPendingApproval] = useState<PendingApproval | null>(null);
  const [isApprovalActionPending, setIsApprovalActionPending] = useState(false);
  const [isRejectFlowOpen, setIsRejectFlowOpen] = useState(false);
  const [approvalFeedback, setApprovalFeedback] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const currentRunMetaRef = useRef<{ runId: string; historyQuery: string; requestKind: "default" | "weekly_review" } | null>(null);
  const timelineListRef = useRef<HTMLDivElement | null>(null);
  const historyPopoverRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("alchemy-theme", theme);
  }, [theme]);

  useEffect(() => {
    window.localStorage.setItem(CONTEXT_HISTORY_KEY, JSON.stringify(contextHistory));
  }, [contextHistory]);

  useEffect(() => {
    if (!isHistoryOpen) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      if (historyPopoverRef.current && !historyPopoverRef.current.contains(event.target as Node)) {
        setIsHistoryOpen(false);
      }
    };

    window.addEventListener("mousedown", handlePointerDown);
    return () => window.removeEventListener("mousedown", handlePointerDown);
  }, [isHistoryOpen]);

  useEffect(() => {
    if (!timelineListRef.current || streamState.logs.length === 0) {
      return;
    }

    timelineListRef.current.scrollTop = timelineListRef.current.scrollHeight;
  }, [streamState.logs]);

  useEffect(() => {
    const loadDataSourceStatus = async () => {
      try {
        const response = await fetch("/api/datasource/status");
        const payload = await readJsonPayload(response);
        if (!response.ok) {
          throw new Error(String(payload.detail ?? `Datasource status request failed with status ${response.status}`));
        }

        setDataSource({
          configured: Boolean(payload.configured),
          provider: typeof payload.provider === "string" ? payload.provider : "",
          databaseLabel: typeof payload.database_label === "string" ? payload.database_label : "",
          message: typeof payload.message === "string" ? payload.message : initialDataSourceState.message,
          executionMode: payload.execution_mode === "pro" ? "pro" : "non_pro",
          accessMode: payload.access_mode === "read_only" ? "read_only" : "write_enabled",
          status: payload.configured ? "connected" : "idle",
        });
      } catch (error) {
        setDataSource({
          configured: false,
          provider: "",
          databaseLabel: "",
          message: (error as Error).message,
          executionMode: "non_pro",
          accessMode: "write_enabled",
          status: "error",
        });
      }
    };

    void loadDataSourceStatus();
  }, []);

  const totalTodos = streamState.todos.length;
  const completedTodos = streamState.todos.filter((todo) => todo.status === "completed").length;
  const streamEventCount = streamState.logs.length;
  const rowCount = streamState.queryResult.length;
  const timelineLogs = useMemo(() => [...streamState.logs].reverse(), [streamState.logs]);
  const activeContextEntry = useMemo(() => contextHistory.find((entry) => entry.id === contextId) ?? null, [contextHistory, contextId]);
  const isRetrying = useMemo(
    () => streamState.status === "running" && streamState.logs.some((log) => isRetrySignalText(`${log.type} ${log.message} ${log.source ?? ""}`)),
    [streamState.logs, streamState.status],
  );
  const sqlStatementCount = useMemo(() => getSqlStatementCount(streamState.generatedSql), [streamState.generatedSql]);
  const isModeSwitchInFlight = dataSource.status === "updating_mode";

  const runLabel = useMemo(() => {
    if (streamState.status === "running") {
      return "Running";
    }
    if (streamState.status === "awaiting_approval") {
      return "Awaiting approval";
    }
    if (streamState.status === "completed") {
      return "Completed";
    }
    if (streamState.status === "error") {
      return "Error";
    }
    return "Idle";
  }, [streamState.status]);

  const handleStreamEvent = (envelope: StreamEnvelope) => {
    const payload = (envelope.data && typeof envelope.data === "object" ? envelope.data : {}) as Record<string, unknown>;
    const source = typeof payload.source === "string" ? payload.source : undefined;
    const judgeCommentary = typeof payload.commentary === "string" ? payload.commentary : "";
    const judgeAttempt = typeof payload.attempt === "number" ? payload.attempt : undefined;
    const judgeReasons = Array.isArray(payload.reasons)
      ? payload.reasons.filter((reason): reason is string => typeof reason === "string" && reason.trim().length > 0)
      : [];

    setStreamState((current) => {
      switch (envelope.event) {
        case "start":
          setPendingApproval(null);
          setIsRejectFlowOpen(false);
          setApprovalFeedback("");
          return {
            ...initialState,
            status: "running",
            logs: appendLog(current.logs, envelope.event, String(payload.message ?? "Agent execution started"), source),
            judgeTranscript: [],
          };
        case "todos":
          if (current.status === "completed" || current.status === "error") {
            return current;
          }
          return {
            ...current,
            todos: Array.isArray(payload.todos) ? (payload.todos as TodoItem[]) : current.todos,
            logs: appendLog(current.logs, envelope.event, "Execution plan updated", source),
          };
        case "step":
          if (current.status === "completed" || current.status === "error") {
            return current;
          }
          return {
            ...current,
            logs: appendLog(current.logs, envelope.event, String(payload.detail ?? "Step updated"), source),
          };
        case "llm_reasoning":
          if (current.status === "completed" || current.status === "error") {
            return current;
          }
          return {
            ...current,
            logs: appendLog(current.logs, envelope.event, String(payload.reasoning ?? "Drafting response"), source),
          };
        case "sql_generated":
          return {
            ...current,
            generatedSql: String(payload.sql ?? current.generatedSql),
            logs: appendLog(current.logs, envelope.event, "Generated SQL", source),
            judgeTranscript: appendJudgeTranscript(
              current.judgeTranscript,
              "llm",
              formatJudgeSqlReviewMessage(judgeAttempt, String(payload.sql ?? "")),
              "left",
            ),
          };
        case "judge_started":
          return {
            ...current,
            judgeStatus: "reviewing",
            judgeReasons: [],
            judgeCommentary: formatJudgeAwaitingMessage(judgeAttempt),
            logs: appendLog(current.logs, envelope.event, judgeCommentary || "Awaiting Approval", source),
            judgeTranscript: appendJudgeTranscript(current.judgeTranscript, "llm", formatJudgeAwaitingMessage(judgeAttempt), "left"),
          };
        case "judge_approved":
          return {
            ...current,
            judgeStatus: "approved",
            judgeReasons: judgeReasons,
            judgeCommentary: formatJudgeApprovedMessage(judgeAttempt, judgeCommentary || "Approved. Executing SQL."),
            logs: appendLog(current.logs, envelope.event, judgeCommentary || "Approved. Executing SQL.", source),
            judgeTranscript: appendJudgeTranscript(
              current.judgeTranscript,
              "judge",
              formatJudgeApprovedMessage(judgeAttempt, judgeCommentary || "Approved. Executing SQL."),
              "right",
              "approved",
            ),
          };
        case "judge_rejected":
          {
            const nextTranscript = appendJudgeTranscript(
              current.judgeTranscript,
              "judge",
              formatJudgeRejectedMessage(judgeAttempt, judgeCommentary, judgeReasons),
              "right",
              "rejected",
            );

            return {
              ...current,
              judgeStatus: "rejected",
              judgeReasons: judgeReasons,
              judgeCommentary: formatJudgeRejectedMessage(judgeAttempt, judgeCommentary, judgeReasons),
              logs: appendLog(current.logs, envelope.event, judgeCommentary || judgeReasons.join("; ") || "Judge rejected SQL.", source),
              judgeTranscript: appendJudgeTranscript(nextTranscript, "llm", formatJudgeRegenerationMessage((judgeAttempt ?? 0) + 1), "left"),
            };
          }
        case "approval_required":
          setIsRejectFlowOpen(false);
          setApprovalFeedback("");
          setPendingApproval({
            approvalId: String(payload.approval_id ?? ""),
            sql: String(payload.sql ?? current.generatedSql),
            commentary: judgeCommentary || "Human approval required before execution in pro mode.",
            reasons: judgeReasons,
            executionMode: payload.execution_mode === "non_pro" ? "non_pro" : "pro",
            attempt: judgeAttempt,
          });
          return {
            ...current,
            status: "awaiting_approval",
            generatedSql: String(payload.sql ?? current.generatedSql),
            judgeStatus: "awaiting_approval",
            judgeReasons: judgeReasons,
            judgeCommentary: formatHumanApprovalMessage(judgeAttempt, judgeCommentary),
            logs: appendLog(current.logs, envelope.event, judgeCommentary || "Human approval required before execution in pro mode.", source),
            judgeTranscript: appendJudgeTranscript(
              current.judgeTranscript,
              "judge",
              formatHumanApprovalMessage(judgeAttempt, judgeCommentary),
              "right",
              "approved",
            ),
          };
        case "query_error":
          return {
            ...current,
            status: "error",
            todos: failOpenTodos(current.todos),
            latestError: String(payload.error ?? "Unknown query error"),
            logs: appendLog(current.logs, envelope.event, String(payload.error ?? "Query execution failed"), source),
          };
        case "final":
          return {
            ...current,
            status: "completed",
            todos: finalizeTodos(Array.isArray(payload.todos) ? (payload.todos as TodoItem[]) : current.todos),
            generatedSql: String(payload.generated_sql ?? current.generatedSql),
            responseSummary: String(payload.response_summary ?? ""),
            queryResult: Array.isArray(payload.query_result) ? (payload.query_result as Array<Record<string, unknown>>) : [],
            logs: appendLog(current.logs, envelope.event, "Run completed successfully", source),
            judgeTranscript: current.judgeTranscript,
          };
        case "error":
          return {
            ...current,
            status: "error",
            todos: failOpenTodos(current.todos),
            latestError: String(payload.message ?? "Unknown stream error"),
            logs: appendLog(current.logs, envelope.event, String(payload.message ?? "Stream error"), source),
          };
        default:
          return {
            ...current,
            logs: appendLog(current.logs, envelope.event, "Received stream event", source),
          };
      }
    });
  };

  const startAgentRun = async (query: string, historyQuery?: string, requestKind: "default" | "weekly_review" = "default") => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const normalizedHistoryQuery = (historyQuery ?? query).trim();
    const normalizedQuery = query.trim();
    currentRunMetaRef.current = {
      runId: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      historyQuery: normalizedHistoryQuery,
      requestKind,
    };

    setPendingApproval(null);
    setIsRejectFlowOpen(false);
    setApprovalFeedback("");

    setContextHistory((current) => {
      const existing = current.find((item) => item.id === contextId);
      const nextEntry: ContextHistoryEntry = existing
        ? {
            ...existing,
            updatedAt: new Date().toLocaleString(),
            lastQuery: normalizedHistoryQuery,
            snapshot: buildRunningSnapshot(contextId),
            runHistory: Array.isArray(existing.runHistory) ? existing.runHistory : [],
          }
        : {
            id: contextId,
            title: buildContextTitle(normalizedHistoryQuery, contextId),
            lastQuery: normalizedHistoryQuery,
            updatedAt: new Date().toLocaleString(),
            snapshot: buildRunningSnapshot(contextId),
            runHistory: [],
          };

      return [nextEntry, ...current.filter((item) => item.id !== contextId)].slice(0, 12);
    });

    setStreamState(buildRunningSnapshot(contextId));

    try {
      await streamDeepAgent(
        {
          context_id: contextId,
          human_query: normalizedQuery,
          request_kind: requestKind,
        },
        controller.signal,
        handleStreamEvent,
      );

      setStreamState((current) => {
        if (current.status !== "running") {
          return current;
        }

        return {
          ...current,
          status: "completed",
          todos: finalizeTodos(current.todos),
          logs: appendLog(current.logs, "final", "Stream closed after final payload was rendered"),
        };
      });
    } catch (error) {
      if ((error as Error).name === "AbortError") {
        currentRunMetaRef.current = null;
        setStreamState((current) => ({
          ...current,
          status: current.status === "completed" ? current.status : "idle",
          logs: appendLog(current.logs, "cancelled", "Streaming request cancelled"),
        }));
        return;
      }

      setStreamState((current) => ({
        ...current,
        status: "error",
        todos: failOpenTodos(current.todos),
        latestError: (error as Error).message,
        logs: appendLog(current.logs, "error", (error as Error).message),
      }));
      currentRunMetaRef.current = null;
    }
  };

  const handleApprovePendingSql = async () => {
    if (!pendingApproval) {
      return;
    }

    setIsApprovalActionPending(true);

    try {
      const response = await fetch(`/api/approvals/${pendingApproval.approvalId}/approve`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ reviewer_comment: "Approved from the UI PoC modal." }),
      });

      const payload = (await response.json()) as {
        status?: string;
        detail?: string;
        approval_id?: string;
        generated_sql?: string;
        query_result?: Array<Record<string, unknown>>;
        response_summary?: string;
        judge_commentary?: string;
        judge_reasons?: string[];
        execution_mode?: "pro" | "non_pro";
      };

      if (!response.ok) {
        throw new Error(payload.detail ?? `Approval failed with status ${response.status}`);
      }

      if (payload.status === "needs_human_approval" && payload.approval_id) {
        const commentary = String(payload.judge_commentary ?? "Regenerated SQL requires human approval.");
        const reasons = Array.isArray(payload.judge_reasons) ? payload.judge_reasons : [];
        setPendingApproval({
          approvalId: payload.approval_id,
          sql: String(payload.generated_sql ?? ""),
          commentary,
          reasons,
          executionMode: payload.execution_mode === "non_pro" ? "non_pro" : "pro",
        });
        setStreamState((current) => ({
          ...current,
          status: "awaiting_approval",
          generatedSql: String(payload.generated_sql ?? current.generatedSql),
          judgeStatus: "awaiting_approval",
          judgeCommentary: commentary,
          judgeReasons: reasons,
          logs: appendLog(current.logs, "approval_required", commentary, "human_approval"),
          judgeTranscript: appendJudgeTranscript(
            current.judgeTranscript,
            "judge",
            commentary,
            "right",
            "approved",
          ),
        }));
        return;
      }

      setStreamState((current) => ({
        ...current,
        status: "completed",
        todos: finalizeTodos(current.todos),
        generatedSql: String(payload.generated_sql ?? pendingApproval.sql),
        queryResult: Array.isArray(payload.query_result) ? payload.query_result : [],
        responseSummary: String(payload.response_summary ?? "Approved SQL executed successfully."),
        latestError: "",
        judgeStatus: "approved",
        logs: appendLog(current.logs, "approval_approved", "Human approval granted. SQL executed."),
        judgeTranscript: appendJudgeTranscript(current.judgeTranscript, "llm", formatHumanApprovalExecutionMessage(), "left", "approved"),
      }));
      setPendingApproval(null);
    } catch (error) {
      setStreamState((current) => ({
        ...current,
        status: "error",
        latestError: (error as Error).message,
        logs: appendLog(current.logs, "approval_error", (error as Error).message),
      }));
    } finally {
      setIsApprovalActionPending(false);
    }
  };

  const handleRejectPendingSql = async () => {
    if (!pendingApproval) {
      return;
    }

    if (!approvalFeedback.trim()) {
      return;
    }

    setIsApprovalActionPending(true);

    try {
      const response = await fetch(`/api/approvals/${pendingApproval.approvalId}/reject`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ reviewer_comment: approvalFeedback.trim() }),
      });

      const payload = (await response.json()) as {
        detail?: string;
        response_summary?: string;
      };

      if (!response.ok) {
        throw new Error(payload.detail ?? `Reject failed with status ${response.status}`);
      }

      const followupQuery = buildHumanRejectionFollowupQuery(humanQuery, pendingApproval.sql, approvalFeedback);
      await startAgentRun(followupQuery, humanQuery.trim());
    } catch (error) {
      setStreamState((current) => ({
        ...current,
        status: "error",
        latestError: (error as Error).message,
        logs: appendLog(current.logs, "approval_error", (error as Error).message),
      }));
    } finally {
      setIsApprovalActionPending(false);
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (isModeSwitchInFlight) {
      setStreamState((current) => ({
        ...current,
        latestError: "Wait for the execution mode switch to finish before running the agent.",
        logs: appendLog(current.logs, "validation", "Execution mode is still updating. Wait for the switch to complete before running a query."),
      }));
      return;
    }

    if (!humanQuery.trim()) {
      setStreamState((current) => ({
        ...current,
        latestError: "Enter a plain-English query before running the agent.",
        logs: appendLog(current.logs, "validation", "Enter a plain-English query before running the agent."),
      }));
      return;
    }

    await startAgentRun(humanQuery.trim(), humanQuery.trim());
  };

  const handleWeeklyReviewClick = async () => {
    if (isModeSwitchInFlight || streamState.status === "running" || streamState.status === "awaiting_approval") {
      return;
    }

    const injectedPrompt = buildWeeklyReviewPrompt(contextId, activeContextEntry?.runHistory ?? []);

    setHumanQuery("");
    await startAgentRun(injectedPrompt, "Weekly review report", "weekly_review");
  };

  const handleStop = () => {
    abortRef.current?.abort();
  };

  const handleResetContext = () => {
    setContextId(createContextId());
    setHumanQuery("");
    setStreamState(initialState);
    setIsHistoryOpen(false);
  };

  const handleSelectContext = (selectedContextId: string) => {
    const selected = contextHistory.find((entry) => entry.id === selectedContextId);
    if (!selected) {
      return;
    }

    setContextId(selected.id);
    setHumanQuery(selected.lastQuery);
    setStreamState(normalizeStoredSnapshot(selected.snapshot));
    setIsHistoryOpen(false);
  };

  useEffect(() => {
    if (!contextId.trim()) {
      return;
    }

    setContextHistory((current) => {
      const existing = current.find((entry) => entry.id === contextId);
      if (!existing) {
        return current;
      }

      const nextEntry: ContextHistoryEntry = {
        ...existing,
        snapshot: streamState,
        runHistory: Array.isArray(existing.runHistory) ? existing.runHistory : [],
      };

      return [nextEntry, ...current.filter((item) => item.id !== contextId)].slice(0, 12);
    });
  }, [contextId, streamState]);

  useEffect(() => {
    const runMeta = currentRunMetaRef.current;
    if (!runMeta || streamState.status !== "completed") {
      return;
    }

    const generatedSql = streamState.generatedSql.trim();
    const responseSummary = streamState.responseSummary.trim();
    if (!generatedSql && !responseSummary) {
      currentRunMetaRef.current = null;
      return;
    }

    const historyEntry: ContextRunHistoryEntry = {
      id: runMeta.runId,
      title: runMeta.requestKind === "weekly_review" ? "Weekly review report" : buildContextTitle(runMeta.historyQuery, contextId),
      userQuery: runMeta.historyQuery,
      generatedSql,
      responseSummary,
      rowCount: streamState.queryResult.length,
      executedAt: new Date().toLocaleString(),
      requestKind: runMeta.requestKind,
    };

    setContextHistory((current) => {
      const existing = current.find((entry) => entry.id === contextId);
      if (!existing) {
        return current;
      }

      const runHistory = Array.isArray(existing.runHistory) ? existing.runHistory : [];
      if (runHistory.some((run) => run.id === historyEntry.id)) {
        return current;
      }

      const nextEntry: ContextHistoryEntry = {
        ...existing,
        runHistory: [historyEntry, ...runHistory].slice(0, 24),
      };

      return [nextEntry, ...current.filter((item) => item.id !== contextId)].slice(0, 12);
    });

    currentRunMetaRef.current = null;
  }, [contextId, streamState.generatedSql, streamState.queryResult.length, streamState.responseSummary, streamState.status]);

  const handleConnectDatasource = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!connectionUrl.trim()) {
      setDataSource((current) => ({
        ...current,
        status: "error",
        message: "Connection URL is required.",
      }));
      return;
    }

    setDataSource((current) => ({
      ...current,
      status: "saving",
      message: "Validating PostgreSQL connection...",
    }));

    try {
      const response = await fetch("/api/datasource/connect", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          provider: "postgres",
          connection_url: connectionUrl.trim(),
        }),
      });

      const payload = await readJsonPayload(response);

      if (!response.ok) {
        throw new Error(String(payload.detail ?? `Datasource connection failed with status ${response.status}`));
      }

      setDataSource({
        configured: Boolean(payload.configured),
        provider: typeof payload.provider === "string" ? payload.provider : "postgres",
        databaseLabel: typeof payload.database_label === "string" ? payload.database_label : "",
        message: typeof payload.message === "string" ? payload.message : "PostgreSQL datasource connected.",
        executionMode: payload.execution_mode === "pro" ? "pro" : "non_pro",
        accessMode: payload.access_mode === "read_only" ? "read_only" : "write_enabled",
        status: "connected",
      });
      setIsDataSourcePickerOpen(false);
      setIsPostgresFormOpen(false);
      setConnectionUrl("");
    } catch (error) {
      setDataSource((current) => ({
        ...current,
        status: "error",
        message: (error as Error).message,
      }));
    }
  };

  const handleDisconnectDatasource = async () => {
    setDataSource((current) => ({
      ...current,
      status: "disconnecting",
      message: "Disconnecting datasource...",
    }));

    try {
      const response = await fetch("/api/datasource/disconnect", {
        method: "POST",
      });

      const payload = await readJsonPayload(response);

      if (!response.ok) {
        throw new Error(String(payload.detail ?? `Datasource disconnect failed with status ${response.status}`));
      }

      setDataSource({
        configured: Boolean(payload.configured),
        provider: typeof payload.provider === "string" ? payload.provider : "",
        databaseLabel: typeof payload.database_label === "string" ? payload.database_label : "",
        message: typeof payload.message === "string" ? payload.message : "Datasource disconnected.",
        executionMode: payload.execution_mode === "pro" ? "pro" : "non_pro",
        accessMode: payload.access_mode === "read_only" ? "read_only" : "write_enabled",
        status: payload.configured ? "connected" : "idle",
      });
      setIsDataSourcePickerOpen(false);
      setIsPostgresFormOpen(false);
      setConnectionUrl("");
    } catch (error) {
      setDataSource((current) => ({
        ...current,
        status: "error",
        message: (error as Error).message,
      }));
    }
  };

  const handleExecutionModeChange = async (executionMode: DataSourceState["executionMode"]) => {
    if (dataSource.executionMode === executionMode) {
      return;
    }

    const environmentLabel = executionMode === "pro" ? "Pro" : "Non-Pro";
    setDataSource((current) => ({
      ...current,
      status: "updating_mode",
      message: `Switching execution mode to ${environmentLabel}...`,
    }));

    try {
      const response = await fetch("/api/execution-mode", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ execution_mode: executionMode }),
      });

      const payload = await readJsonPayload(response);

      if (!response.ok) {
        throw new Error(String(payload.detail ?? `Execution mode update failed with status ${response.status}`));
      }

      setDataSource({
        configured: Boolean(payload.configured),
        provider: typeof payload.provider === "string" ? payload.provider : "",
        databaseLabel: typeof payload.database_label === "string" ? payload.database_label : "",
        message: typeof payload.message === "string" ? payload.message : `${environmentLabel} mode active.`,
        executionMode: payload.execution_mode === "pro" ? "pro" : executionMode,
        accessMode: payload.access_mode === "read_only" ? "read_only" : executionMode === "pro" ? "read_only" : "write_enabled",
        status: payload.configured ? "connected" : "idle",
      });
    } catch (error) {
      setDataSource((current) => ({
        ...current,
        status: "error",
        message: (error as Error).message,
      }));
    }
  };

  return (
    <main className={`shell ${streamState.status === "running" ? "agent-running" : ""}`}>
      <div className="ambient ambient-a" />
      <div className="ambient ambient-b" />
      <div className="ambient ambient-c" />

      <section className="hero cinematic-hero">
        <div className="hero-copy-block">
          <div className="hero-topbar">
            <div className="hero-utility-stack">
              <ThemeToggleButton
                theme={theme}
                onToggle={() => setTheme((current) => (current === "dark" ? "light" : "dark"))}
              />
            </div>
          </div>
          <p className="eyebrow">Text-to-SQL AI Agent</p>
          <h1 className="hero-glass-title">Text-to-SQL AI Agent for Dashboard Summaries</h1>
          <p className="hero-copy large-copy">
            Convert plain-English questions into environment-aware SQL operations, summarize results for daily or weekly reviews,
            and work from a single connected database with schema discovery.
          </p>

          <div className="stat-grid">
            <StatCard label="Status" value={runLabel} tone="teal" />
            <StatCard label="Tasks" value={`${completedTodos}/${Math.max(totalTodos, 1)}`} tone="amber" />
            <StatCard label="Rows" value={String(rowCount)} tone="violet" />
          </div>
        </div>

        <div className="hero-card cinematic-card">
          <div className="panel-header hero-card-header">
            <span className={`status-pill ${streamState.status}`}>{streamState.status}</span>
            <div className="hero-badge-cluster">
              <span className="hero-badge">{getExecutionModeLabel(dataSource.executionMode)}</span>
              <span className={`hero-badge access-badge ${dataSource.accessMode}`}>{getAccessModeLabel(dataSource.accessMode)}</span>
            </div>
          </div>

          <div className="thinking-lane" aria-hidden="true">
            <span className="thinking-chip" />
            <span className="thinking-chip" />
            <span className="thinking-chip" />
            <span className="thinking-chip" />
          </div>

          <div className="hero-runtime-grid">
            <div>
              <p className="hero-label">Plain English query</p>
              <strong>DeepAgent orchestrator</strong>
            </div>
            <div>
              <p className="hero-label">Connected database</p>
              <strong>{dataSource.databaseLabel || "Awaiting DB URL"}</strong>
            </div>
          </div>

          <div className="hero-signal-bar">
            <span />
            <span />
            <span />
            <span />
          </div>

          <p className="muted">Supports multi-table joins, follow-up context, and environment-aware execution rules.</p>

          <div className="mini-metrics">
            <div>
              <span>Events</span>
              <strong>{streamEventCount}</strong>
            </div>
            <div>
              <span>Context ID</span>
              <strong>{contextId.slice(0, 8)}</strong>
            </div>
          </div>
        </div>
      </section>

      <section className="layout">
        <div className="stack">
          <DataSourcePanel
            dataSource={dataSource}
            isPickerOpen={isDataSourcePickerOpen}
            isPostgresFormOpen={isPostgresFormOpen}
            connectionUrl={connectionUrl}
            onOpenPicker={() => setIsDataSourcePickerOpen(true)}
            onClosePicker={() => {
              setIsDataSourcePickerOpen(false);
              setIsPostgresFormOpen(false);
            }}
            onChoosePostgres={() => {
              setIsDataSourcePickerOpen(true);
              setIsPostgresFormOpen(true);
            }}
            onConnectionUrlChange={setConnectionUrl}
            onSubmit={handleConnectDatasource}
            onDisconnect={handleDisconnectDatasource}
            onExecutionModeChange={handleExecutionModeChange}
          />

          <section className="panel input-panel hero-panel query-panel">
            <div className="panel-header">
              <div className="section-heading compact">
                <p className="eyebrow">Plain English query</p>
                <h2>Ask the AI agent</h2>
              </div>
              <div className="query-panel-header-actions">
                <button
                  type="button"
                  className="primary-button cinematic-button"
                  onClick={() => void handleWeeklyReviewClick()}
                  disabled={streamState.status === "running" || streamState.status === "awaiting_approval" || isModeSwitchInFlight}
                >
                  Weekly review
                </button>
                <button type="button" className="ghost-button luminous-button" onClick={handleResetContext}>
                  New context
                </button>
              </div>
            </div>

            <form onSubmit={handleSubmit} className="query-form">
              <label>
                Saved conversations
                <div className="history-popover" ref={historyPopoverRef}>
                  <button
                    type="button"
                    className={`history-trigger ${isHistoryOpen ? "is-open" : ""}`}
                    onClick={() => setIsHistoryOpen((current) => !current)}
                    aria-haspopup="listbox"
                    aria-expanded={isHistoryOpen}
                  >
                    <span className="history-trigger-copy">
                      <strong>{activeContextEntry?.title ?? "Choose a previous conversation"}</strong>
                      <span>{activeContextEntry?.updatedAt ?? "Saved by context ID and first executed query"}</span>
                    </span>
                    <span className="history-trigger-icon" aria-hidden="true" />
                  </button>

                  {isHistoryOpen ? (
                    <div className="history-menu" role="listbox" aria-label="Saved conversations">
                      {contextHistory.length === 0 ? (
                        <div className="history-empty">No saved conversations yet.</div>
                      ) : (
                        contextHistory.map((entry) => (
                          <button
                            key={entry.id}
                            type="button"
                            className={`history-option ${entry.id === contextId ? "active" : ""}`}
                            onClick={() => handleSelectContext(entry.id)}
                          >
                            <span className="history-option-title">{entry.title}</span>
                            <span className="history-option-meta">{`${entry.id.slice(0, 8)} - ${entry.updatedAt}`}</span>
                          </button>
                        ))
                      )}
                    </div>
                  ) : null}
                </div>
              </label>
              <label>
                Context ID
                <input value={contextId} onChange={(event) => setContextId(event.target.value)} />
              </label>
              <p className="muted context-helper-copy">Use the same Context ID to continue the same conversation, or choose a saved conversation to continue from where you left off.</p>
              <label>
                Human query
                <textarea
                  rows={5}
                  value={humanQuery}
                  onChange={(event) => setHumanQuery(event.target.value)}
                  placeholder="Summarize open high-priority cases for the weekly review"
                />
              </label>
              <div className="button-row">
                <button type="submit" className="primary-button cinematic-button" disabled={streamState.status === "running" || streamState.status === "awaiting_approval" || isModeSwitchInFlight}>
                  {streamState.status === "running"
                    ? "Streaming..."
                    : streamState.status === "awaiting_approval"
                      ? "Awaiting approval..."
                      : isModeSwitchInFlight
                        ? "Switching mode..."
                        : "Run deep agent"}
                </button>
                <button type="button" className="ghost-button luminous-button" onClick={handleStop}>
                  Stop process
                </button>
              </div>
            </form>
          </section>

          <TodoPanel todos={streamState.todos} isLoading={streamState.status === "running"} />

          {streamState.status === "error" && streamState.latestError ? <FailureCallout message={streamState.latestError} /> : null}

          <JudgeTerminalPanel
            transcript={streamState.judgeTranscript}
            judgeStatus={streamState.judgeStatus}
            commentary={streamState.judgeCommentary}
          />

          <SummaryPanel summary={streamState.responseSummary} status={streamState.status} statementCount={sqlStatementCount} />

          <GeneratedSqlPanel sql={streamState.generatedSql} status={streamState.status} rowCount={streamState.queryResult.length} isRetrying={isRetrying} />

          <ResultTable rows={streamState.queryResult} statementCount={sqlStatementCount} sql={streamState.generatedSql} />
        </div>

        <aside className="panel timeline-panel glass-panel hero-panel">
          <div className="panel-header">
            <div className="section-heading compact">
              <p className="eyebrow">Execution steps</p>
              <h2>Timeline</h2>
            </div>
            <strong>{streamState.logs.length} events</strong>
          </div>

          {streamState.status === "running" ? (
            <div className="timeline-thinking" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
          ) : null}

          <div className="timeline-list" ref={timelineListRef}>
            {timelineLogs.length === 0 ? (
              <p className="muted">No stream events yet.</p>
            ) : (
              timelineLogs.map((log, index) => (
                <article key={log.id} className="timeline-item glass-timeline-item" style={{ animationDelay: `${Math.min(index * 72, 504)}ms` }}>
                  <div className="timeline-meta">
                    <span className="timeline-sequence">{index + 1}</span>
                    <span className="timeline-type">{getTimelineTypeLabel(log.type)}</span>
                    <span className="timeline-timestamp">
                      <ClockIcon />
                      <span>{log.timestamp}</span>
                    </span>
                  </div>
                  <p>{log.message}</p>
                </article>
              ))
            )}
          </div>
        </aside>
      </section>

      {pendingApproval ? (
        <ApprovalModal
          approval={pendingApproval}
          isSubmitting={isApprovalActionPending}
          isRejectFlowOpen={isRejectFlowOpen}
          feedback={approvalFeedback}
          onFeedbackChange={setApprovalFeedback}
          onApprove={() => void handleApprovePendingSql()}
          onBeginReject={() => setIsRejectFlowOpen(true)}
          onCancelReject={() => {
            setIsRejectFlowOpen(false);
            setApprovalFeedback("");
          }}
          onConfirmReject={() => void handleRejectPendingSql()}
        />
      ) : null}
    </main>
  );
}

export default App;