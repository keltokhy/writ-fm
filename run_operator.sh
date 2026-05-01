#!/bin/bash
# WRIT-FM Operator - Launch Claude Code for maintenance
# Run manually, via cron, or from mac/operator_daemon.sh.

set -euo pipefail

# Cron runs with a minimal PATH; ensure Homebrew-installed CLIs are available.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$HOME/.local/bin"

cd "$(dirname "$0")"

LOG_DIR="output"
SESSION_LOG="$LOG_DIR/operator_session_$(date +%Y-%m-%d).log"
HEARTBEAT_SECONDS="${WRIT_OPERATOR_HEARTBEAT_SECONDS:-30}"
CLAUDE_TIMEOUT_SECONDS="${WRIT_OPERATOR_TIMEOUT_SECONDS:-1800}"

mkdir -p "$LOG_DIR"

LOCK_DIR="$LOG_DIR/operator.lock"
acquire_lock() {
    if mkdir "$LOCK_DIR" 2>/dev/null; then
        echo "$$" > "$LOCK_DIR/pid"
        trap 'rm -rf "$LOCK_DIR"' EXIT
        return 0
    fi

    local old_pid=""
    old_pid="$(cat "$LOCK_DIR/pid" 2>/dev/null || true)"
    if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
        echo "[operator] another run is active pid=$old_pid; skipping"
        exit 0
    fi

    rm -rf "$LOCK_DIR"
    mkdir "$LOCK_DIR"
    echo "$$" > "$LOCK_DIR/pid"
    trap 'rm -rf "$LOCK_DIR"' EXIT
}

acquire_lock

# Read the operator prompt
PROMPT=$(cat mac/operator_prompt.md)

# Launch Claude Code with the prompt and append the full session transcript.
echo | tee -a "$SESSION_LOG"
echo "## operator session $(date '+%Y-%m-%d %H:%M:%S %Z')" | tee -a "$SESSION_LOG"

TIMEOUT_BIN="$(command -v timeout || command -v gtimeout || true)"
CLAUDE_CMD=(claude -p "$PROMPT" --allowedTools "Bash,Read,Write,Edit,Glob,Grep")
if [ -n "$TIMEOUT_BIN" ]; then
    CLAUDE_CMD=("$TIMEOUT_BIN" "$CLAUDE_TIMEOUT_SECONDS" "${CLAUDE_CMD[@]}")
fi

"${CLAUDE_CMD[@]}" \
    > >(tee -a "$SESSION_LOG") \
    2> >(tee -a "$SESSION_LOG" >&2) &
CLAUDE_PID=$!

echo "[operator] pid=$CLAUDE_PID" | tee -a "$SESSION_LOG"

heartbeat() {
    local pid="$1"
    while kill -0 "$pid" 2>/dev/null; do
        sleep "$HEARTBEAT_SECONDS"
        kill -0 "$pid" 2>/dev/null || break
        echo "[operator] heartbeat $(date '+%Y-%m-%d %H:%M:%S %Z') pid=$pid" | tee -a "$SESSION_LOG" >/dev/null
    done
}

heartbeat "$CLAUDE_PID" &
HEARTBEAT_PID=$!

set +e
wait "$CLAUDE_PID"
STATUS=$?
set -e

kill "$HEARTBEAT_PID" 2>/dev/null || true
wait "$HEARTBEAT_PID" 2>/dev/null || true

if [ "$STATUS" -eq 124 ]; then
    echo "[operator] timed out after ${CLAUDE_TIMEOUT_SECONDS}s" | tee -a "$SESSION_LOG"
fi
echo "[operator] exit status=$STATUS $(date '+%Y-%m-%d %H:%M:%S %Z')" | tee -a "$SESSION_LOG"

exit "$STATUS"
