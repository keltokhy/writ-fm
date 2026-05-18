#!/usr/bin/env python3
"""
WRIT-FM Chatterbox TTS Module

Resemble AI's Chatterbox (0.5B params). Supports voice cloning from a short
reference WAV. Slower than Kokoro but more expressive and clone-capable.

Setup:
    cd mac/chatterbox
    uv venv
    uv pip install chatterbox-tts soundfile torch torchaudio 'setuptools<81'

Apple Silicon: torch picks up MPS automatically; this script selects mps if
torch.backends.mps.is_available() is True.

Note: setuptools<81 is required because Chatterbox's `perth` watermarker
imports `pkg_resources`, which setuptools 81+ removed. With newer setuptools
the watermarker silently fails to import and `ChatterboxTTS.__init__` blows
up with "'NoneType' object is not callable".

Usage:
    python tts.py "Hello world" -o out.wav
    python tts.py "Hello world" -o out.wav --voice path/to/reference.wav
"""

import os
import subprocess
from pathlib import Path

CHATTERBOX_DIR = Path(__file__).parent
VENV_PYTHON = CHATTERBOX_DIR / ".venv" / "bin" / "python"

# Chatterbox has no named voices — it's clone-from-reference. The default
# uses Chatterbox's built-in baseline voice.
DEFAULT_VOICE = ""


def setup_venv():
    """Create and set up the chatterbox venv if it doesn't exist."""
    venv_dir = CHATTERBOX_DIR / ".venv"
    if not venv_dir.exists():
        print("Setting up Chatterbox venv...")
        subprocess.run(["uv", "venv"], cwd=CHATTERBOX_DIR, check=True)
        subprocess.run(
            ["uv", "pip", "install", "chatterbox-tts", "soundfile", "torch", "torchaudio", "setuptools<81"],
            cwd=CHATTERBOX_DIR,
            check=True,
        )
        print("Chatterbox venv ready")
    return VENV_PYTHON.exists()


def render_speech(
    text: str,
    output_path: Path,
    voice: str = DEFAULT_VOICE,
    exaggeration: float = 0.5,
    cfg_weight: float = 0.5,
) -> bool:
    """
    Render text to speech using Chatterbox TTS.

    Args:
        text: The text to speak.
        output_path: Where to save the WAV file.
        voice: Path to a reference WAV for voice cloning, or "" for the
            default Chatterbox voice.
        exaggeration: Emotion intensity 0.0-1.0 (0.5 = neutral, higher = more expressive).
        cfg_weight: Classifier-free guidance weight 0.0-1.0.

    Returns:
        True if successful, False otherwise.
    """
    if not VENV_PYTHON.exists():
        if not setup_venv():
            print("Failed to set up Chatterbox venv")
            return False

    # Subprocess runs with cwd=CHATTERBOX_DIR; resolve so relative paths still work.
    output_path = Path(output_path).resolve()
    # Escape text for embedding in Python string literal
    escaped_text = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    escaped_voice = voice.replace("\\", "\\\\").replace('"', '\\"') if voice else ""

    tts_script = f'''
import warnings
warnings.filterwarnings("ignore")

import torch
import torchaudio as ta
from chatterbox.tts import ChatterboxTTS

if torch.cuda.is_available():
    device = "cuda"
elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
    device = "mps"
else:
    device = "cpu"

model = ChatterboxTTS.from_pretrained(device=device)

text = "{escaped_text}"
voice_path = "{escaped_voice}"

kwargs = {{"exaggeration": {exaggeration}, "cfg_weight": {cfg_weight}}}
if voice_path:
    kwargs["audio_prompt_path"] = voice_path

wav = model.generate(text, **kwargs)
ta.save("{output_path}", wav, model.sr)
print("SUCCESS")
'''

    try:
        result = subprocess.run(
            [str(VENV_PYTHON), "-c", tts_script],
            capture_output=True,
            text=True,
            timeout=600,  # 10 min — Chatterbox is slower than Kokoro
            cwd=str(CHATTERBOX_DIR),
        )
        if "SUCCESS" in result.stdout:
            return True
        print(f"Chatterbox error: {result.stderr}")
        return False
    except subprocess.TimeoutExpired:
        print("Chatterbox timed out")
        return False
    except Exception as e:
        print(f"TTS error: {e}")
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Chatterbox TTS renderer")
    parser.add_argument("text", help="Text to speak")
    parser.add_argument("-o", "--output", default="test.wav", help="Output WAV file")
    parser.add_argument(
        "-v",
        "--voice",
        default=DEFAULT_VOICE,
        help="Reference WAV path for voice cloning (omit for default voice)",
    )
    parser.add_argument(
        "--exaggeration", type=float, default=0.5, help="Emotion intensity (0.0-1.0)"
    )
    parser.add_argument(
        "--cfg-weight", type=float, default=0.5, help="CFG guidance weight (0.0-1.0)"
    )
    args = parser.parse_args()

    success = render_speech(
        args.text,
        Path(args.output),
        voice=args.voice,
        exaggeration=args.exaggeration,
        cfg_weight=args.cfg_weight,
    )
    print("Success!" if success else "Failed")
