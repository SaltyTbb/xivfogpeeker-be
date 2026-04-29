# xivFogPeeker — Backend

Go backend for xivFogPeeker. Fetches FFLogs data via GraphQL and runs AI analysis via DeepSeek.

## Setup

```bash
cp .env.example .env
# fill in FFLOGS_CLIENT_ID, FFLOGS_CLIENT_SECRET, DEEPSEEK_API_KEY
go mod tidy
go run .
```

Server runs on `http://localhost:8080`.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/report/:code` | List fights in a report (for fight picker) |
| `POST` | `/analyze` | Analyze a specific fight, returns structured data + LLM summary |
| `POST` | `/chat` | Follow-up Q&A with fight context |

## Project structure

```
internal/
  fflogs/     FFLogs OAuth2 client + GraphQL queries
  llm/        DeepSeek chat client
  analysis/   Data processor (raw events → structured summary)
  handler/    HTTP route handlers
```
