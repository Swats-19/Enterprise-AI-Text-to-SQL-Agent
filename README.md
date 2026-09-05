# AI Text-to-SQL Agent

An AI-powered system that lets users query an e-commerce database using natural language instead of writing SQL manually.

## Why This Project?

SQL is powerful, but querying a database usually requires users to understand tables, relationships, joins, and SQL syntax. LLMs make natural-language database interaction possible, but simply asking an LLM to generate SQL is not always reliable — a query can be syntactically valid while still being logically wrong.

This project explores a simple question:

**What happens when we move from a single LLM call to a controlled, self-correcting AI workflow?**

To demonstrate this, I built the same Text-to-SQL problem using **two different architectures**.

## 1. Monolithic Architecture

The baseline implementation keeps the workflow simple:

```text
User Question
      ↓
     LLM
      ↓
 Generated SQL
      ↓
   Database
      ↓
    Result
```

It is straightforward and works well for simple queries, but there is no independent validation or recovery step between SQL generation and execution.

## 2. Agentic Architecture

The second implementation uses **LangGraph** to turn the pipeline into a multi-step workflow:

```text
User Question
      ↓
Database Connection
      ↓
Schema Loading
      ↓
Schema Filtering
      ↓
SQL Generator
      ↓
SQL Judge
   ↙       ↘
Reject    Approve
  ↓          ↓
Regenerate  Human Approval
              ↓
        ┌─────┴─────┐
      Reject       Approve
        ↓             ↓
    Regenerate     Execute
                      ↓
                 Explain Result
```

### Why is this better?

The agentic version adds **verification and recovery** instead of blindly trusting the first LLM response.

* **SQL Judge** — independently evaluates the generated SQL
* **Self-Healing** — rejected SQL is regenerated using the judge's feedback
* **Human-in-the-Loop** — the user can approve, reject, or provide feedback before execution
* **Checkpointing** — the workflow can pause and resume without losing state
* **Observability** — LangSmith tracks the workflow, LLM calls, retries, latency and token usage
* **Multi-Provider LLMs** — supports fallback across configured LLM providers

The goal is not just to generate SQL, but to make the AI workflow **more reliable, controllable, and observable**.

## Why AI?

Natural language is a much more accessible interface to data than requiring every user to know SQL.

AI can translate a question such as:

> "Show me the top 5 customers by total spending."

into a database query without requiring the user to understand the underlying schema or SQL syntax.

The challenge is making that translation trustworthy. That is where the validation, retry, human approval, and observability layers become important.

## Demo

**5-Minute Pitch Video:**
[[Add YouTube link]](https://youtu.be/1b8nx-9ISZw)

The demo shows:

1. A normal successful query
2. SQL Judge rejection and automatic regeneration
3. Human-in-the-Loop approval and workflow resumption
4. LangSmith traces showing what happened inside the workflow

## Tech Stack

* Python
* LangGraph
* LangChain
* Streamlit
* SQLite / PostgreSQL
* Gemini / Groq / Cohere
* LangSmith

## Run Locally

For complete first-time installation, PostgreSQL setup, testing, and
troubleshooting, see [FIRST_TIME_SETUP.md](FIRST_TIME_SETUP.md).

Create and activate an isolated Python environment:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and configure `DATABASE_URL` plus at least
`GEMINI_API_KEY_1`.

Install the React UI:

```powershell
Set-Location ui
npm install
```

Start both the API and UI:

```powershell
.\start-app.ps1
```

Open `http://127.0.0.1:5173`.

Stop both services with:

```powershell
.\stop-app.ps1
```

The React interface communicates with the existing LangGraph workflow through
server-sent events. Pro mode pauses for human approval; Non-Pro mode
automatically approves the query. Both modes enforce read-only SQL.

## Project Structure

```text
text_to_sql/
├── database/
├── skills/
├── ui/
├── api.py
├── llm.py
├── prompt.py
├── text_to_sql.py
├── execute.py
├── mon.py
└── skills.py
```

**Developer : Swati Muttin**

## Built For
**Razorpay AI Buildathon**

This project focuses on a real problem — making database access easier through natural language — while exploring how **agentic AI can improve reliability beyond a basic LLM pipeline**.
