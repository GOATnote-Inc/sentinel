#!/usr/bin/env bash
# One command to run SENTINEL.   ./demo.sh            (live model if a key is available)
#                                ./demo.sh --offline  (venue-wifi-proof: cached plans)
# Key discovery: SENTINEL_ENV_FILE > ./.env > already-exported ANTHROPIC_API_KEY.
# No key + no --offline just degrades to deterministic plans, honestly labeled in the UI.
set -euo pipefail
cd "$(dirname "$0")"

ENV_FILE="${SENTINEL_ENV_FILE:-.env}"
if [ -f "$ENV_FILE" ]; then
  set -a; # shellcheck disable=SC1090
  source "$ENV_FILE"; set +a
fi

PY=".venv/bin/python"
if [ ! -x "$PY" ]; then
  python3 -m venv .venv
  .venv/bin/pip install --quiet -r requirements.txt
fi

echo "SENTINEL starting on http://localhost:${SENTINEL_PORT:-8787}  (feed auto-starts in ${SENTINEL_START_DELAY:-6}s — open the browser now)"
exec "$PY" -m sentinel.app "$@"
