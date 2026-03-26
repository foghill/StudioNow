#!/bin/bash
# Run the scraper using the project venv — bypasses system Python
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
"$SCRIPT_DIR/.venv/bin/python" -m scraper.cli "$@"
