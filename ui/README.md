# TextToSQL UI

This folder contains a standalone React UI for the existing FastAPI backend.

## Run

From the repository root:

```powershell
.\ui\start.ps1
```

The script installs dependencies on first run and then starts the Vite dev server at `http://127.0.0.1:5173`.

## Backend integration

- UI requests are sent to `/api/deep-agent/stream`.
- Vite proxies `/api/*` to `http://127.0.0.1:8000/*`.
- This avoids browser CORS failures without modifying the backend.

## Stream events handled

- `start`
- `step`
- `todos`
- `sql_generated`
- `llm_reasoning`
- `query_error`
- `final`
- `error`

## Todo shape

The UI accepts todo items that follow the deep-agent pattern and prefers these fields when rendering labels:

1. `content`
2. `title`
3. `description`

Status values are rendered for `pending`, `in_progress`, and `completed`.