#!/usr/bin/env python3
"""
One-time migration: move flat talk_segments into archive/legacy/.

Before the slot-keyed layout, content lived directly under
`output/talk_segments/{show_id}/*.wav`. That content has no slot assignment
and must not play under the new architecture. Move it all to
`output/archive/legacy/{show_id}/` so it's preserved but inert.

Anything already inside a slot subfolder (matches YYYY-MM-DD_HHMM) is left
alone. Anything else at the top of each show folder gets moved.

Idempotent. Safe to re-run.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TALK_DIR = PROJECT_ROOT / "output" / "talk_segments"
LEGACY_DIR = PROJECT_ROOT / "output" / "archive" / "legacy"

SLOT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{4}$")


def main() -> int:
    if not TALK_DIR.exists():
        print(f"No talk_segments/ at {TALK_DIR} — nothing to do.")
        return 0

    moved = 0
    for show_dir in sorted(TALK_DIR.iterdir()):
        if not show_dir.is_dir():
            continue
        # Skip empty placeholder test dirs
        loose_files = [p for p in show_dir.iterdir() if p.is_file()]
        if not loose_files:
            # Remove it if it has no slot subfolders either
            subdirs = [d for d in show_dir.iterdir() if d.is_dir()]
            if not subdirs:
                show_dir.rmdir()
            continue

        dest = LEGACY_DIR / show_dir.name
        dest.mkdir(parents=True, exist_ok=True)

        for p in loose_files:
            target = dest / p.name
            if target.exists():
                # Filename collision across runs — suffix and move on
                i = 1
                while (dest / f"{p.stem}.{i}{p.suffix}").exists():
                    i += 1
                target = dest / f"{p.stem}.{i}{p.suffix}"
            p.rename(target)
            moved += 1

        print(f"  {show_dir.name}: moved {len(loose_files)} → archive/legacy/")

    print(f"\nDone. Moved {moved} file(s) to {LEGACY_DIR}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
