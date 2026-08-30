#!/bin/bash
# Endless supervisor daemon script for Contour-Based Pond Catchment Analysis API
# Maintains Uvicorn server instances continuously on ports 3245 and 3000

cd "$(dirname "$0")"

run_port() {
    local port=$1
    while true; do
        echo "[$(date)] Starting Uvicorn server on port $port..." >> "uvicorn_$port.log"
        python3 -m uvicorn app.main:app --host 0.0.0.0 --port "$port" >> "uvicorn_$port.log" 2>&1
        echo "[$(date)] Server process on port $port exited with code $?. Auto-restarting in 2 seconds..." >> "uvicorn_$port.log"
        sleep 2
    done
}

# Run daemons for both port 3245 and port 3000 continuously
run_port 3245 &
run_port 3000 &

# Wait for child processes
wait
