#!/usr/bin/env bash
set -euo pipefail

backend_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
frontend_dir="$(cd "$backend_dir/../FossxHacktober-ui/frontend" && pwd)"
python_bin="$backend_dir/.venv/bin/python"
db_path="${LARA_DB_PATH:-${XDG_DATA_HOME:-$HOME/.local/share}/ubuntu-agent/ubuntu-agent.sqlite3}"
public_origin="http://127.0.0.1:5173"
api_pid=''
frontend_pid=''

if [[ ! -x "$python_bin" ]]; then
  printf 'Python environment missing at %s. Create it and install the project dependencies first.\n' "$python_bin" >&2
  exit 1
fi
if [[ ! -d "$frontend_dir/node_modules" ]]; then
  printf 'Frontend dependencies missing. Run npm --prefix "%s" install first.\n' "$frontend_dir" >&2
  exit 1
fi
if ! command -v node >/dev/null 2>&1 || [[ ! -x "$frontend_dir/node_modules/.bin/vite" ]]; then
  printf 'Node.js and the local Vite executable are required. Install the frontend dependencies first.\n' >&2
  exit 1
fi

# This launcher is intentionally localhost-only. It never creates pairing credentials or a tunnel.
export LARA_LOCAL_DEMO=1
export UBUNTU_AGENT_API_ORIGINS="$public_origin"
unset LARA_PUBLIC_ORIGIN

check_port() {
  "$python_bin" - "$1" <<'PY'
import socket, sys
port = int(sys.argv[1])
sock = socket.socket()
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    sock.bind(("127.0.0.1", port))
except OSError:
    raise SystemExit(f"Port {port} is already in use; stop the existing LARA process or choose another port.")
finally:
    sock.close()
PY
}
check_port 8765
check_port 5173

cleanup() {
  trap - EXIT INT TERM
  if [[ -n "$frontend_pid" ]]; then
    kill -TERM "$frontend_pid" 2>/dev/null || true
    wait "$frontend_pid" 2>/dev/null || true
  fi
  if [[ -n "$api_pid" ]]; then
    kill -TERM "$api_pid" 2>/dev/null || true
    wait "$api_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

cd "$backend_dir"
"$python_bin" -m ubuntu_agent --db "$db_path" init
"$python_bin" -m ubuntu_agent --db "$db_path" api-serve --host 127.0.0.1 --port 8765 &
api_pid=$!

# Wait for the API, then report model and memory readiness separately. Missing Ollama or
# Qdrant keeps unrelated local screens usable but is made explicit to the operator.
"$python_bin" - <<'PY'
import json, time, urllib.error, urllib.request
url = "http://127.0.0.1:8765/api/v1/ready"
deadline = time.monotonic() + 30
last_error = "not responding"
while time.monotonic() < deadline:
    try:
        request = urllib.request.Request(url, headers={"Origin":"http://127.0.0.1:5173"})
        with urllib.request.urlopen(request, timeout=2) as response:
            data = json.load(response)
        break
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        last_error = type(exc).__name__
        time.sleep(0.4)
else:
    raise SystemExit(f"Local backend did not become ready ({last_error}).")
if data.get("database") != "ready":
    raise SystemExit("Local backend database is not ready.")
model = data.get("local_model", {})
memory = data.get("memory", {})
print(f"Backend ready; local model: {model.get('status', 'unknown')} ({model.get('model', 'not configured')}).")
print(f"Conversational memory: {memory.get('status', 'unknown')} ({memory.get('embedding_model', 'embedding model unknown')}).")
if model.get("status") != "available":
    print("Ollama/model is unavailable. Chat and AI Loops will report inference errors until it is started/configured.")
if memory.get("status") != "ready":
    print("Local embedding/Qdrant memory is degraded; chat remains available and indexing status will be reported.")
PY

cd "$frontend_dir"
"$frontend_dir/node_modules/.bin/vite" --host 127.0.0.1 --port 5173 --strictPort &
frontend_pid=$!
"$python_bin" - <<'PY'
import time, urllib.error, urllib.request
url = "http://127.0.0.1:5173/"
deadline = time.monotonic() + 30
while time.monotonic() < deadline:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            if response.status == 200 and "text/html" in response.headers.get("Content-Type", ""):
                break
    except (OSError, urllib.error.URLError, TimeoutError):
        time.sleep(0.3)
else:
    raise SystemExit("Frontend did not become ready on 127.0.0.1:5173.")
PY

printf '\nLARA IV local demo is ready at %s\n' "$public_origin"
printf 'No pairing is required. The API is bound to 127.0.0.1:8765.\n'
printf 'Stop this command with Ctrl+C to stop Vite and the backend.\n\n'

wait "$frontend_pid"
