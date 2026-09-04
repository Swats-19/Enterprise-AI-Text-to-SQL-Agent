export type TodoStatus = "pending" | "in_progress" | "completed" | string;

export interface TodoItem {
  status: TodoStatus;
  content?: string;
  title?: string;
  description?: string;
}

export interface StreamEnvelope {
  event: string;
  data: unknown;
}

export interface StreamLog {
  id: string;
  type: string;
  source?: string;
  message: string;
  timestamp: string;
}

export interface JudgeTranscriptEntry {
  id: string;
  speaker: "llm" | "judge";
  side: "left" | "right";
  tone: "neutral" | "approved" | "rejected";
  message: string;
  timestamp: string;
}

export interface PendingApproval {
  approvalId: string;
  sql: string;
  commentary: string;
  reasons: string[];
  executionMode: "pro" | "non_pro";
  attempt?: number;
}

export interface StreamState {
  status: "idle" | "running" | "awaiting_approval" | "completed" | "error";
  todos: TodoItem[];
  logs: StreamLog[];
  generatedSql: string;
  responseSummary: string;
  queryResult: Array<Record<string, unknown>>;
  latestError: string;
  judgeStatus: "idle" | "reviewing" | "awaiting_approval" | "approved" | "rejected";
  judgeReasons: string[];
  judgeCommentary: string;
  judgeTranscript: JudgeTranscriptEntry[];
}