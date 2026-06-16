#!/bin/sh
# Start the Blaxel sandbox API, then idle. The SDK / `bl` / preview URLs all talk
# to this API on :8080. Processes (dev servers, Claude Code, agent-browser) are
# launched on demand through that API, so we just keep it alive here.
set -e

export PATH="/usr/local/bin:$PATH"

/usr/local/bin/sandbox-api &

wait_for_port() {
    port=$1
    timeout=30
    count=0
    echo "Waiting for sandbox API on port $port..."
    while ! nc -z 127.0.0.1 "$port"; do
        sleep 1
        count=$((count + 1))
        if [ "$count" -gt "$timeout" ]; then
            echo "Timeout waiting for port $port"
            exit 1
        fi
    done
    echo "Sandbox API ready on :$port"
}

wait_for_port 8080

wait
