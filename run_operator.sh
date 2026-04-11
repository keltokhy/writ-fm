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

mkdir -p "$LOG_DIR"

# Read the operator prompt
PROMPT=$(cat mac/operator_prompt.md)

# Launch Claude Code with the prompt and append the full session transcript.
echo | tee -a "$SESSION_LOG"
echo "## operator session $(date '+%Y-%m-%d %H:%M:%S %Z')" | tee -a "$SESSION_LOG"

claude -p "$PROMPT" --allowedTools "Bash,Read,Write,Edit,Glob,Grep" \
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

wait "$CLAUDE_PID"
STATUS=$?

kill "$HEARTBEAT_PID" 2>/dev/null || true
wait "$HEARTBEAT_PID" 2>/dev/null || true

echo "[operator] exit status=$STATUS $(date '+%Y-%m-%d %H:%M:%S %Z')" | tee -a "$SESSION_LOG"

exit "$STATUS"
