#!/usr/bin/env python3
"""
WRIT-FM TTS A/B test helper.

Renders the same text through one (or all) TTS engines so you can compare
outputs side-by-side without booting any daemons.

Usage:
    uv run python mac/tts_test.py kokoro "Hello from Kokoro"
    uv run python mac/tts_test.py chatterbox "Hello from Chatterbox" --voice samples/me.wav
    uv run python mac/tts_test.py voxtral "Hello from Voxtral" --voice casual_female
    uv run python mac/tts_test.py all "Compare every engine on the same line"

Outputs land in output/tts-test/ as `tts-test-{engine}-{timestamp}.wav`.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "mac"))
sys.path.insert(0, str(PROJECT_ROOT / "mac" / "content_generator"))

# Import the per-engine renderers directly. We deliberately bypass the dispatch
# layer here so each --engine flag really does test that engine.
from helpers import (  # type: ignore  # noqa: E402
    render_kokoro,
    render_chatterbox,
    render_voxtral,
    get_audio_duration,
    log,
)

ENGINES = ("kokoro", "chatterbox", "voxtral")
DEFAULT_OUT_DIR = PROJECT_ROOT / "output" / "tts-test"


def render_one(engine: str, text: str, voice: str | None, out_dir: Path) -> Path | None:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"tts-test-{engine}-{ts}.wav"

    if engine == "kokoro":
        ok = render_kokoro(text, out_path, voice or "am_michael")
    elif engine == "chatterbox":
        ok = render_chatterbox(text, out_path, voice or "")
    elif engine == "voxtral":
        ok = render_voxtral(text, out_path, voice or "casual_male")
    else:
        log(f"Unknown engine: {engine}")
        return None

    if not ok or not out_path.exists():
        log(f"  [{engine}] FAILED")
        return None

    dur = get_audio_duration(out_path)
    dur_str = f"{dur:.1f}s" if dur else "?"
    log(f"  [{engine}] OK -> {out_path.relative_to(PROJECT_ROOT)} ({dur_str})")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="A/B test WRIT-FM TTS engines.")
    parser.add_argument(
        "engine",
        choices=(*ENGINES, "all"),
        help="Engine to render with, or 'all' for every engine.",
    )
    parser.add_argument("text", help="Text to speak.")
    parser.add_argument(
        "-v", "--voice",
        default=None,
        help="Engine-specific voice id or reference WAV path. Engine default if omitted.",
    )
    parser.add_argument(
        "-o", "--out-dir",
        default=str(DEFAULT_OUT_DIR),
        help=f"Directory to write samples into (default: {DEFAULT_OUT_DIR.relative_to(PROJECT_ROOT)}).",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir).expanduser()
    if not out_dir.is_absolute():
        out_dir = PROJECT_ROOT / out_dir

    engines = ENGINES if args.engine == "all" else (args.engine,)

    successes = 0
    for eng in engines:
        # Don't pass a voice flag through to engines that didn't ask for it
        # unless the user is targeting a single engine.
        voice = args.voice if args.engine != "all" else None
        if render_one(eng, args.text, voice, out_dir) is not None:
            successes += 1

    print()
    log(f"Done: {successes}/{len(engines)} engine(s) rendered.")
    return 0 if successes == len(engines) else 1


if __name__ == "__main__":
    raise SystemExit(main())
