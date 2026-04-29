# xivFogPeeker — Backend

Python backend for xivFogPeeker. Fetches FFLogs data and runs a LangGraph agent pipeline to analyse deaths and performance, then summarises with DeepSeek.

## Setup

```bash
cp .env.example .env
# fill in FFLOGS_CLIENT_ID, FFLOGS_CLIENT_SECRET, DEEPSEEK_API_KEY

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python main.py
```

Server runs on `http://localhost:8080`.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/report/{code}` | List fights in a report (for fight picker) |
| `POST` | `/analyze` | Run full LangGraph analysis, returns structured data + LLM summary |
| `POST` | `/chat` | Follow-up Q&A with fight context |

## LangGraph pipeline

```
fetch_data
    ├── death_analyst      (parallel)
    └── performance_analyst (parallel)
            └── summariser
```

## Project structure

```
app/
  api/        FastAPI routes + Pydantic models
  fflogs/     FFLogs OAuth2 client + async GraphQL queries
  graph/      LangGraph state, nodes, and graph assembly
  analysis/   Hardcoded reference data (raid buff IDs, etc.)
```
