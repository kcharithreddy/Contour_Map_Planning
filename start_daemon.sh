#!/bin/bash
# Endless supervisor daemon script for Contour-Based Pond Catchment Analysis API
# Maintains Uvicorn server instances continuously on ports 3245 and 3000

cd "$(dirname "$0")"

export PATH="$HOME/.local/bin:$PATH"

PYTHON_BIN="python3"
if [ -f "./.venv/bin/python3" ] && ./.venv/bin/python3 -c "import uvicorn" 2>/dev/null; then
    PYTHON_BIN="./.venv/bin/python3"
elif python3 -c "import uvicorn" 2>/dev/null; then
    PYTHON_BIN="python3"
fi

run_port() {
    local port=$1
    while true; do
        echo "[$(date)] Starting Uvicorn server on port $port..." >> "uvicorn_$port.log"
        "$PYTHON_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port "$port" >> "uvicorn_$port.log" 2>&1
        echo "[$(date)] Server process on port $port exited with code $?. Auto-restarting in 2 seconds..." >> "uvicorn_$port.log"
        sleep 2
    done
}

# Run daemons for both port 3245 and port 3000 continuously
run_port 3245 &
run_port 3000 &

# Wait for child processes
wait
