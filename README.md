# LARA IV

LARA IV is a local-first productivity workspace with a React/Vite frontend and a
Python API backed by SQLite. Its local Ollama chat and AI Loops are optional;
task, reminder, and conversation data persist locally.

## Repository layout

- `backend/` — FastAPI API, SQLite schema and migrations, services, CLI, and tests.
- `frontend/` — React/Vite application, UI assets, local API adapter, and mock fixtures.
- `scripts/` — local development launchers.
- `Docs/` — product, security, API, data, and operations specifications.

## Requirements

- Python 3.11 or newer
- Node.js 20.19+ or 22.12+ (required by Vite 8)
- npm
- Optional for local inference: [Ollama](https://ollama.com/)
- Optional for retrieval-backed memory: the Qdrant client extra and Ollama's
  `embeddinggemma` model. Qdrant uses local embedded storage; no separate server
  is required.

## Install

From the repository root:

```sh
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install --upgrade pip
backend/.venv/bin/python -m pip install -e 'backend[test]'
npm --prefix frontend ci
cp .env.example .env
```

Edit `.env` only if you need optional provider settings. It is ignored by Git.
The `GEMINI_API_KEY` entry is optional; the normal local workflow uses Ollama
and does not require a cloud key.

To enable local chat and AI Loop inference, install/start Ollama and fetch the
default model:

```sh
ollama pull gemma4:e2b-it-q4_K_M
```

To enable local conversational retrieval memory, install its optional backend
dependency and fetch the embedding model:

```sh
backend/.venv/bin/python -m pip install -e 'backend[rag]'
ollama pull embeddinggemma
```

Without the optional Qdrant client or embedding model, the API remains available
and reports memory readiness as degraded.

## Run locally

```sh
./scripts/start-lara-local.sh
```

Open <http://127.0.0.1:5173>. The launcher uses explicit local-demo mode, binds
the API and Vite to loopback only, waits for both HTTP services to become ready,
and stops both processes on exit or Ctrl+C. It does not open a pairing dialog or
start ngrok. It uses `LARA_DB_PATH` when set; otherwise it stores the SQLite
database at `${XDG_DATA_HOME:-~/.local/share}/ubuntu-agent/lara-demo.sqlite3`.
The launcher runs schema initialization against that selected database without
resetting its contents.
The default ports are 8765 (API) and 5173 (frontend); set `LARA_API_PORT` or
`LARA_FRONTEND_PORT` to use alternate ports when those defaults are occupied.

To choose a disposable database for a demo, set the path before starting:

```sh
mkdir -p /tmp/lara-iv-demo
LARA_DB_PATH=/tmp/lara-iv-demo/lara.sqlite3 ./scripts/start-lara-local.sh
```

## Demo data

Seeding is an explicit CLI operation; it never clears the chosen database.
Repeated seeding is idempotent, preserves edits and non-demo records, and adds
synthetic tasks, conversations, reminders, projects, calendar events, and sample
AI Loop records without running inference:

```sh
backend/.venv/bin/python -m ubuntu_agent \
  --db /tmp/lara-iv-demo/lara.sqlite3 \
  seed-demo --environment development
backend/.venv/bin/python -m ubuntu_agent \
  --db /tmp/lara-iv-demo/lara.sqlite3 demo-status
```

Use a new disposable path when you want a clean demo. Never point destructive
experiments at a database containing user data.

## Development and tests

Run the complete backend test suite:

```sh
backend/.venv/bin/python -m pytest backend/tests
```

Compile backend modules and check whitespace:

```sh
backend/.venv/bin/python -m compileall -q backend/ubuntu_agent backend/tests
git diff --check
```

Build and lint the frontend:

```sh
LARA_LOCAL_DEMO=1 npm --prefix frontend run build
npm --prefix frontend run lint
```

The API and frontend are separate dev servers: run the backend CLI with
`api-serve --host 127.0.0.1 --port 8765` from `backend/`, then run Vite from
`frontend/` with `npm run dev -- --host 127.0.0.1 --port 5173`. Vite proxies
`/api` to the loopback backend. The integrated launcher configures this for you.

## Configuration and security

`LARA_LOCAL_DEMO=1` is reserved for the local launcher and requires loopback
binding plus an explicitly configured local frontend origin. Outside that mode,
the API's pairing, origin checks, and other deployment protections remain
enabled. Do not expose the local API to untrusted callers.

Useful optional settings include `OLLAMA_MODEL`, `OLLAMA_TIMEOUT_SECONDS`,
`UBUNTU_AGENT_OLLAMA_URL`, `UBUNTU_AGENT_EMBEDDING_MODEL`, and `GEMINI_API_KEY`.
The backend reads `GEMINI_API_KEY` from the process environment or the root
`.env` file; provider status never prints credential values. Never commit `.env`,
database files, local vector stores, model weights, virtual environments, or
`node_modules`.

## Troubleshooting

- **Missing Python environment or packages:** repeat the Python setup commands
  above from the repository root.
- **Missing Vite executable:** run `npm --prefix frontend ci`.
- **Port 8765 or 5173 is occupied:** stop the process already using the port,
  then retry.
- **Chat or AI Loops report inference unavailable:** start Ollama and pull the
  configured model. The rest of the local application remains usable.
- **Memory readiness is degraded:** check that the configured local Ollama
  embedding model and Qdrant service are available.
- **Browser shows no backend:** use the root launcher so the Vite `/api` proxy
  and matching loopback CORS origin are configured together.
