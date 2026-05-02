#!/bin/bash
# WRIT-FM Operator Daemon — runs the Claude maintenance loop on an interval.
# This replaces the separate talk and bumper stocking daemons.

set -euo pipefail

RADIO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
INTERVAL_SECONDS="${WRIT_OPERATOR_INTERVAL_SECONDS:-900}"

ts() { date +%H:%M; }

echo "[operator-daemon $(ts)] Starting. Interval: ${INTERVAL_SECONDS}s"

while true; do
    echo "[operator-daemon $(ts)] Running operator loop..."
    (
        cd "$RADIO_DIR"
        ./run_operator.sh
    ) || echo "[operator-daemon $(ts)] operator pass exited with status $?; continuing"
    echo "[operator-daemon $(ts)] Sleeping ${INTERVAL_SECONDS}s..."
    sleep "$INTERVAL_SECONDS"
done
