#!/bin/bash
# Supervisor daemon for Remote Node:
# Frontend on port 3000
# Backend on port 6000

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

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

# Kill any existing processes on 3000 and 6000
fuser -k 3000/tcp >/dev/null 2>&1 || true
fuser -k 6000/tcp >/dev/null 2>&1 || true

# Run Backend on Port 6000
run_backend() {
    while true; do
        echo "[$(date)] Starting Backend Uvicorn server on port 6000 using $PYTHON_BIN..." >> "$DIR/backend_6000.log"
        "$PYTHON_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port 6000 >> "$DIR/backend_6000.log" 2>&1
        echo "[$(date)] Backend on port 6000 exited with code $?. Auto-restarting in 2s..." >> "$DIR/backend_6000.log"
        sleep 2
    done
}

# Run Frontend on Port 3000
run_frontend() {
    while true; do
        echo "[$(date)] Starting Frontend Uvicorn server on port 3000 using $PYTHON_BIN..." >> "$DIR/frontend_3000.log"
        BACKEND_URL="http://127.0.0.1:6000" "$PYTHON_BIN" -m uvicorn frontend_server:app --host 0.0.0.0 --port 3000 >> "$DIR/frontend_3000.log" 2>&1
        echo "[$(date)] Frontend on port 3000 exited with code $?. Auto-restarting in 2s..." >> "$DIR/frontend_3000.log"
        sleep 2
    done
}

run_backend &
run_frontend &

wait
