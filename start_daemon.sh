#!/bin/bash
# Endless supervisor daemon script for Contour-Based Pond Catchment Analysis API
# Maintains Uvicorn server instances continuously on ports 3245 and 3000

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

export PATH="$DIR/.venv/bin:$HOME/.local/bin:$PATH"

PYTHON_BIN="python3"
if [ -x "$DIR/.venv/bin/python3" ]; then
    PYTHON_BIN="$DIR/.venv/bin/python3"
elif [ -x "./.venv/bin/python3" ]; then
    PYTHON_BIN="./.venv/bin/python3"
fi

run_port() {
    local port=$1
    while true; do
        echo "[$(date)] Starting Uvicorn server on port $port..." >> "$DIR/uvicorn_$port.log"
        "$PYTHON_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port "$port" >> "$DIR/uvicorn_$port.log" 2>&1
        echo "[$(date)] Server process on port $port exited with code $?. Auto-restarting in 2 seconds..." >> "$DIR/uvicorn_$port.log"
        sleep 2
    done
}

# Run daemons for both port 3245 and port 3000 continuously
run_port 3245 &
run_port 3000 &

# Wait for child processes
wait
