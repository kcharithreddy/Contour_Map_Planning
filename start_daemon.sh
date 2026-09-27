#!/bin/bash
# Endless supervisor daemon script for Contour-Based Pond Catchment Analysis API
# Maintains Uvicorn server instances continuously on ports 3245 and 3000

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Find python interpreter that actually has uvicorn installed
PYTHON_BIN=""
if [ -x "$DIR/.venv/bin/python3" ] && "$DIR/.venv/bin/python3" -c "import uvicorn" >/dev/null 2>&1; then
    export PATH="$DIR/.venv/bin:$PATH"
    PYTHON_BIN="$DIR/.venv/bin/python3"
elif [ -x "$HOME/.venv/bin/python3" ] && "$HOME/.venv/bin/python3" -c "import uvicorn" >/dev/null 2>&1; then
    export PATH="$HOME/.venv/bin:$PATH"
    PYTHON_BIN="$HOME/.venv/bin/python3"
elif command -v python3 >/dev/null 2>&1 && python3 -c "import uvicorn" >/dev/null 2>&1; then
    PYTHON_BIN="$(which python3)"
else
    PYTHON_BIN="python3"
fi

export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:$PATH"

run_port() {
    local port=$1
    while true; do
        echo "[$(date)] Starting Uvicorn server on port $port using $PYTHON_BIN..." >> "$DIR/uvicorn_$port.log"
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
