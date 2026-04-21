#!/bin/bash
# Metadata script for ezstream — called once per track.
# ezstream passes the file path as $1.
#
# Responsibilities:
#   1. Move the PREVIOUS track to aired/ if it lived in a slot folder.
#      This is what enforces "never plays again within the same slot
#      after a crash/restart" — aired files are invisible to the feeder.
#   2. Update state file with the current track's path.
#   3. Print the metadata line ("host - clean_name") for ezstream's
#      @a@ - @t@ format string.
#
# Bumpers (in music_bumpers/) are a shared pool — we never move them.
# Only files inside {show_id}/{YYYY-MM-DD_HHMM}/ get the aired treatment.

set -u

PROJECT_ROOT="/Volumes/K3/agent-working-space/projects/active/2025-12-29-radio-station"
STATE_FILE="$PROJECT_ROOT/output/.current_track.txt"
NOW_PLAYING="$PROJECT_ROOT/output/now_playing.json"

CURRENT="${1:-}"

# Read previous track
PREV=""
[ -f "$STATE_FILE" ] && PREV=$(cat "$STATE_FILE" 2>/dev/null || true)

# Move previous to aired/ if (a) still exists, (b) lives in a slot folder
if [ -n "$PREV" ] && [ -f "$PREV" ]; then
    PREV_DIR=$(dirname "$PREV")
    SLOT_NAME=$(basename "$PREV_DIR")
    if echo "$SLOT_NAME" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{4}$'; then
        AIRED_DIR="$PREV_DIR/aired"
        mkdir -p "$AIRED_DIR"
        mv -f "$PREV" "$AIRED_DIR/" 2>/dev/null || true
    fi
fi

# Record current as "previous" for next invocation (atomic-ish)
if [ -n "$CURRENT" ]; then
    TMP="$STATE_FILE.tmp"
    printf '%s' "$CURRENT" > "$TMP"
    mv -f "$TMP" "$STATE_FILE"
fi

# ── Metadata output ─────────────────────────────────────────────────────────

# Clean display name from filename
name_of() {
    local stem
    stem=$(basename "$1")
    stem="${stem%.*}"
    case "$stem" in
        *listener_response*) echo "Listener Mail" ;;
        *deep_dive*)         echo "Deep Dive" ;;
        *news_analysis*)     echo "Signal Report" ;;
        *interview*)         echo "The Interview" ;;
        *panel*)             echo "Crosswire" ;;
        *story*)             echo "Story Hour" ;;
        *listener_mailbag*)  echo "Listener Hours" ;;
        *music_essay*)       echo "Sonic Essay" ;;
        *show_intro*)        echo "Show Opening" ;;
        *show_outro*)        echo "Show Closing" ;;
        *station_id*)        echo "WRIT-FM" ;;
        *bumper*)            echo "AI Music" ;;
        *)                   echo "Transmission" ;;
    esac
}

HOST="WRIT-FM"
if [ -f "$NOW_PLAYING" ]; then
    H=$(python3 -c "import json,sys; print(json.load(open('$NOW_PLAYING')).get('host','') or '')" 2>/dev/null || true)
    [ -n "$H" ] && HOST="$H"
fi

if [ -n "$CURRENT" ]; then
    TITLE=$(name_of "$CURRENT")
    # Bumpers: prefer display_name from sidecar JSON if present
    BASENAME=$(basename "$CURRENT")
    EXT="${BASENAME##*.}"
    STEM="${BASENAME%.*}"
    META_FILE="$(dirname "$CURRENT")/$STEM.json"
    if [ "$EXT" != "wav" ] && [ -f "$META_FILE" ]; then
        DISPLAY=$(python3 -c "import json; print(json.load(open('$META_FILE')).get('display_name',''))" 2>/dev/null || true)
        [ -n "$DISPLAY" ] && TITLE="$DISPLAY"
    fi
    printf '%s - %s\n' "$HOST" "$TITLE"
else
    # No file path given — fallback to a generic line
    printf '%s - %s\n' "$HOST" "WRIT-FM"
fi
