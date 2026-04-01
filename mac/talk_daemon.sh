#!/bin/bash
# WRIT-FM Talk Daemon — continuously stock talk segments
# Checks segment counts per show, generates when low.
# Each cycle generates for the show with the fewest segments.
# Safe to kill and restart anytime.

RADIO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MIN_SEGMENTS=6       # target segments per show
BATCH_SIZE=2         # segments to generate per cycle
SLEEP_STOCKED=600    # 10min when all shows are above minimum
SLEEP_BETWEEN=30     # 30s pause between generation cycles

ts() { date +%H:%M; }

echo "[talk-daemon $(ts)] Starting. Target: ${MIN_SEGMENTS} segments/show, batch: ${BATCH_SIZE}"

# Unset CLAUDECODE so Claude CLI works inside tmux
unset CLAUDECODE

while true; do
    cd "$RADIO_DIR"

    # Find the show with the fewest segments
    lowest_show=""
    lowest_count=999

    for show_dir in output/talk_segments/*/; do
        [ -d "$show_dir" ] || continue
        show_id="$(basename "$show_dir")"
        count=$(find "$show_dir" -name '*.wav' -o -name '*.mp3' -o -name '*.flac' | wc -l | tr -d ' ')

        if (( count < lowest_count )); then
            lowest_count=$count
            lowest_show=$show_id
        fi
    done

    # If no show directories exist, generate for all
    if [ -z "$lowest_show" ]; then
        echo "[talk-daemon $(ts)] No segment dirs found — generating for all shows"
        uv run python mac/content_generator/talk_generator.py --all --count "$BATCH_SIZE" 2>&1
        echo "[talk-daemon $(ts)] Done. Sleeping ${SLEEP_BETWEEN}s..."
        sleep $SLEEP_BETWEEN
        continue
    fi

    # If lowest is above minimum, everything is stocked
    if (( lowest_count >= MIN_SEGMENTS )); then
        echo "[talk-daemon $(ts)] All shows stocked (lowest: ${lowest_show} = ${lowest_count}). Sleeping ${SLEEP_STOCKED}s..."
        sleep $SLEEP_STOCKED
        continue
    fi

    echo "[talk-daemon $(ts)] ${lowest_show} has ${lowest_count}/${MIN_SEGMENTS} segments — generating ${BATCH_SIZE}..."
    uv run python mac/content_generator/talk_generator.py --show "$lowest_show" --count "$BATCH_SIZE" 2>&1

    echo "[talk-daemon $(ts)] Done. Sleeping ${SLEEP_BETWEEN}s..."
    sleep $SLEEP_BETWEEN
done
