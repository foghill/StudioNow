#!/bin/bash
# Start the Studio Now local API server.
# Requires the .venv to be set up: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
#
# Environment variables:
#   HOST                  Bind address (default: 127.0.0.1)
#   PORT                  Port number (default: 8000)
#   SCRAPE_INTERVAL_HOURS How often to auto-scrape high-priority sources (default: 24)
#                         Set to 0 to disable automatic scraping (manual-only mode)
#   Example: SCRAPE_INTERVAL_HOURS=0 ./serve.sh   # manual-only
#            SCRAPE_INTERVAL_HOURS=12 ./serve.sh  # scrape every 12 hours
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

echo "Studio Now API → http://$HOST:$PORT"
echo "Docs           → http://$HOST:$PORT/docs"
echo ""

"$SCRIPT_DIR/.venv/bin/python" -m uvicorn scraper.server:app \
    --host "$HOST" \
    --port "$PORT" \
    --reload \
    --reload-dir scraper \
    --log-level info