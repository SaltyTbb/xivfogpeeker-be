# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
cp .env.example .env        # fill in credentials
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run
python main.py              # starts on :8080 with --reload

# Add a dependency
pip install <pkg> && pip freeze > requirements.txt
```

No test suite yet — `requirements.txt` is the source of truth for dependencies.

## Architecture

A FastAPI app that orchestrates a LangGraph pipeline. The request lifecycle is:

1. **Route** (`app/api/routes.py`) receives a `POST /analyze` with `report_code` + `fight_id`
2. It builds the LangGraph and calls `graph.ainvoke(initial_state)`
3. The graph runs in this order:
   - `fetch_data` — authenticates with FFLogs OAuth2 and fetches all raw events (deaths, casts, buffs, damage) via GraphQL
   - `death_analyst` + `performance_analyst` — run **in parallel**, each reads from state and writes their own output fields back
   - `summariser` — waits for both analysts, builds a plain-text context string, calls DeepSeek, returns the final summary
4. The route returns `analysis` (structured data), `summary` (LLM text), and `context` (plain text passed back to the client for Q&A)

### LangGraph state

`app/graph/state.py` defines `GraphState` as a single `TypedDict` that flows through the entire graph. Each node receives the full state and returns a partial dict of only the keys it populates. The state is partitioned by phase — inputs → fetch → analysts → summariser.

### FFLogs client

`app/fflogs/client.py` is an async context manager. It authenticates on `__aenter__` and exposes `query()` (raw GraphQL) plus typed helpers (`get_fights`, `get_actors`, `get_events`). All event fetching uses a single `get_events(code, fight_id, data_type)` method where `data_type` maps to FFLogs `EventDataType` enum values (`"Deaths"`, `"Casts"`, `"Buffs"`, `"DamageTaken"`). Pagination via `nextPageTimestamp` is not yet implemented.

### LLM

DeepSeek Chat is called via `langchain-openai`'s `ChatOpenAI` with `base_url="https://api.deepseek.com"`. The LLM instance is constructed in `routes.py` and injected into the `summariser` node via `functools.partial`. The system prompt lives in `app/graph/nodes.py` — it explicitly prohibits suggestions and coaching.

### Raid buff IDs

`app/analysis/buffs.py` contains `RAID_BUFF_IDS` (dict keyed by job abbreviation) and `ALL_RAID_BUFF_IDS` (flat set for O(1) lookups). This is the only place to add/correct buff ability IDs. IDs were sourced from xivapi + community resources and may need verification.

## Key constraints

- The LLM output must remain **observation-only** — no suggestions, no coaching. This is by design for the product.
- Buff/debuff snapshot logic in `death_analyst` and uptime/buff-window logic in `performance_analyst` are stubs marked `TODO M2` and `TODO M3` respectively — these are the next milestones to implement.
- FFLogs API requires OAuth2 client credentials (`FFLOGS_CLIENT_ID` + `FFLOGS_CLIENT_SECRET`). The token is fetched once per request, not cached.
