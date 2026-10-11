#!/usr/bin/env bash
set -euo pipefail

backend_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
frontend_dir="$(cd "$backend_dir/../FossxHacktober-ui/frontend" && pwd)"
python_bin="$backend_dir/.venv/bin/python"
db_path="${LARA_DB_PATH:-${XDG_DATA_HOME:-$HOME/.local/share}/ubuntu-agent/ubuntu-agent.sqlite3}"

if [[ ! -x "$python_bin" ]]; then
  printf 'Python environment missing at %s. Create it and install the project dependencies first.\n' "$python_bin" >&2
  exit 1
fi
if [[ ! -d "$frontend_dir/node_modules" ]]; then
  printf 'Frontend dependencies missing. Run npm --prefix "%s" install first.\n' "$frontend_dir" >&2
  exit 1
fi

cd "$backend_dir"
"$python_bin" -m ubuntu_agent --db "$db_path" init
"$python_bin" -m ubuntu_agent --db "$db_path" api-session-create --origin http://localhost:5173
"$python_bin" -m ubuntu_agent --db "$db_path" api-serve --port 8765 &
api_pid=$!
cleanup() { kill "$api_pid" 2>/dev/null || true; wait "$api_pid" 2>/dev/null || true; }
trap cleanup EXIT INT TERM
cd "$backend_dir"
npm --prefix "$frontend_dir" run dev -- --host 127.0.0.1
