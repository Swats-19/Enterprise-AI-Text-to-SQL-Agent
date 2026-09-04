# First-Time Setup and Test Guide

This guide is for Windows and the `Alchemy007` branch.

## What the application does

The application connects to PostgreSQL, discovers the tables and relationships
in the database's `public` schema, sends the relevant schema to Gemini, generates
read-only SQL, judges the SQL, optionally requests human approval, executes the
query, and displays a result summary.

The database does not need to use the demo e-commerce schema. Table and column
metadata are read from the PostgreSQL database selected in `DATABASE_URL`.

## Prerequisites

Install:

1. Git
2. Python 3.12
3. Node.js 18 or newer
4. PostgreSQL, or network access to an existing PostgreSQL server
5. A Gemini API key

Confirm the tools are available:

```powershell
git --version
py -3.12 --version
node --version
npm --version
```

## 1. Clone the correct branch

```powershell
git clone --branch Alchemy007 --single-branch https://github.com/Swats-19/Enterprise-AI-Text-to-SQL-Agent.git
Set-Location Enterprise-AI-Text-to-SQL-Agent
```

## 2. Create the Python environment

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 3. Install the frontend

```powershell
Set-Location ui
npm install
Set-Location ..
```

## 4. Configure secrets

Create a private `.env` file:

```powershell
Copy-Item .env.example .env
notepad .env
```

Set at least:

```dotenv
DATABASE_URL=postgresql://USERNAME:PASSWORD@HOST:PORT/DATABASE_NAME
GEMINI_API_KEY_1=YOUR_GEMINI_API_KEY
DEFAULT_EXECUTION_MODE=pro
```

Example for local PostgreSQL:

```dotenv
DATABASE_URL=postgresql://postgres:password@localhost:5432/my_database
```

Important:

- URL-encode special characters in the username or password.
- Do not commit or share `.env`.
- The PostgreSQL user needs permission to connect and read the required tables.
- A read-only PostgreSQL account is recommended.
- Schema discovery currently reads regular tables from the `public` schema.

## 5. Start the complete application

From the repository root:

```powershell
.\start-app.ps1
```

If script execution is blocked:

```powershell
powershell -ExecutionPolicy Bypass -File .\start-app.ps1
```

Open:

```text
http://127.0.0.1:5173
```

The backend health endpoint is:

```text
http://127.0.0.1:8000/health
```

It should display:

```json
{"status":"ok"}
```

## 6. Connect PostgreSQL from the UI

If `.env` already contains the correct `DATABASE_URL`, the datasource should
appear as connected automatically.

To change it from the UI:

1. Select **Change data source**.
2. Select **PostgreSQL**.
3. Enter the complete PostgreSQL connection URL.
4. Select **Connect PostgreSQL**.
5. Confirm the datasource card shows **Connected**.

The backend validates the connection and saves the URL to the local `.env`.

## 7. Test schema discovery

Use questions based on tables that really exist in the connected database.
Examples:

```text
List all customers.
```

```text
Show three assets with their asset names and asset types.
```

```text
Count cases by status.
```

The agent automatically:

1. Reads tables, columns, primary keys, and foreign keys.
2. Selects relevant live tables.
3. Gives Gemini the selected schema.
4. Generates PostgreSQL-compatible SQL.
5. Runs the LLM judge.
6. Requests approval in Pro mode.
7. Executes one read-only `SELECT` query.
8. Displays rows and a summary.

## 8. Pro and Non-Pro modes

- **Pro:** pauses and shows the generated SQL for human approval.
- **Non-Pro:** automatically approves after the LLM judge.

Both modes remain read-only. Non-Pro does not enable `INSERT`, `UPDATE`,
`DELETE`, `DROP`, `ALTER`, or multiple SQL statements.

## 9. Run automated tests

Backend:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Frontend production build:

```powershell
Set-Location ui
npm run build
Set-Location ..
```

## 10. Stop the application

```powershell
.\stop-app.ps1
```

## Troubleshooting

### `Failed to fetch`

The UI cannot reach FastAPI. Start both services:

```powershell
.\start-app.ps1
```

Then verify `http://127.0.0.1:8000/health`.

### PostgreSQL authentication failure

Check the username, password, host, port, database name, firewall, and
`pg_hba.conf`. URL-encode special characters in credentials.

### No tables discovered

Confirm the tables are in the PostgreSQL `public` schema and the configured user
can read `information_schema` plus those tables.

### Gemini quota or model error

Wait for the provider quota window to reset, use another configured Gemini key,
or configure one of the optional fallback providers in `.env`.

### Port already in use

Stop the prior application:

```powershell
.\stop-app.ps1
```

Then run `.\start-app.ps1` again.
