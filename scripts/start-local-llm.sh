#!/usr/bin/env bash
# Start llama.cpp's llama-server with the Gemma 2 2B model on the port Prosody
# expects. Foreground process — Ctrl-C to stop, or run via `nohup` / tmux.
#
# Override any of these via env when launching:
#   LLAMA_SERVER_BIN     path to llama-server         (default: llama-server on PATH)
#   LLAMA_SERVER_MODEL   path to .gguf model          (default: Gemma 2 2B Q4_K_M)
#   LLAMA_SERVER_PORT    port to bind                 (default: 8090, matches LOCAL_LLM_BASE_URL)
#   LLAMA_SERVER_CTX     context window               (default: 4096)
#   LLAMA_SERVER_EXTRA   extra flags appended verbatim

set -euo pipefail

BIN="${LLAMA_SERVER_BIN:-llama-server}"
MODEL="${LLAMA_SERVER_MODEL:-/Users/davidloor/models/llm/gemma-2-2b-it-Q4_K_M.gguf}"
PORT="${LLAMA_SERVER_PORT:-8090}"
CTX="${LLAMA_SERVER_CTX:-4096}"
ALIAS="${LLAMA_SERVER_ALIAS:-${LOCAL_LLM_MODEL:-gemma-local}}"
EXTRA="${LLAMA_SERVER_EXTRA:-}"

if ! command -v "$BIN" >/dev/null 2>&1 && [ ! -x "$BIN" ]; then
  echo "llama-server not found on PATH. Install via: brew install llama.cpp" >&2
  exit 1
fi
if [ ! -f "$MODEL" ]; then
  echo "Model file not found: $MODEL" >&2
  echo "Set LLAMA_SERVER_MODEL to a .gguf path." >&2
  exit 1
fi
if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PORT is already in use. Pick another with LLAMA_SERVER_PORT=… or stop the existing process." >&2
  exit 1
fi

echo "Starting llama-server"
echo "  binary : $BIN"
echo "  model  : $MODEL"
echo "  alias  : $ALIAS  (Prosody sends this as the 'model' field; must match LOCAL_LLM_MODEL)"
echo "  port   : $PORT  (Prosody expects LOCAL_LLM_BASE_URL=http://127.0.0.1:$PORT/v1)"
echo "  ctx    : $CTX"
echo
exec "$BIN" -m "$MODEL" --alias "$ALIAS" --port "$PORT" --ctx-size "$CTX" $EXTRA
