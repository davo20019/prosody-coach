#!/usr/bin/env bash
# Start whisper.cpp's whisper-server on the port Prosody expects. Foreground
# process — Ctrl-C to stop, or run via `nohup` / tmux.
#
# Override any of these via env when launching:
#   WHISPER_SERVER_BIN    path to whisper-server      (default: whisper-server on PATH)
#   WHISPER_SERVER_MODEL  path to ggml .bin model     (default: ggml-medium.en.bin)
#   WHISPER_SERVER_PORT   port to bind                (default: 9000, matches LOCAL_WHISPER_SERVER_URL)
#   WHISPER_SERVER_EXTRA  extra flags appended verbatim

set -euo pipefail

BIN="${WHISPER_SERVER_BIN:-whisper-server}"
MODEL="${WHISPER_SERVER_MODEL:-/Users/davidloor/models/whisper/ggml-medium.en.bin}"
PORT="${WHISPER_SERVER_PORT:-9000}"
EXTRA="${WHISPER_SERVER_EXTRA:-}"

if ! command -v "$BIN" >/dev/null 2>&1 && [ ! -x "$BIN" ]; then
  echo "whisper-server not found on PATH. Install via: brew install whisper-cpp" >&2
  exit 1
fi
if [ ! -f "$MODEL" ]; then
  echo "Model file not found: $MODEL" >&2
  echo "Set WHISPER_SERVER_MODEL to a ggml-*.bin path." >&2
  exit 1
fi
if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PORT is already in use. Pick another with WHISPER_SERVER_PORT=… or stop the existing process." >&2
  exit 1
fi

echo "Starting whisper-server"
echo "  binary : $BIN"
echo "  model  : $MODEL"
echo "  port   : $PORT  (Prosody expects LOCAL_WHISPER_SERVER_URL=http://127.0.0.1:$PORT)"
echo
exec "$BIN" -m "$MODEL" --port "$PORT" $EXTRA
