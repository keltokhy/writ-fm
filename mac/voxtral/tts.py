#!/usr/bin/env python3
"""
WRIT-FM Voxtral TTS Module

Mistral AI's Voxtral-4B-TTS-2603 (released March 2026). 4B parameter
multilingual TTS (9 languages), voice cloning from short reference, low latency.

This module uses the MLX port (mlx-community/Voxtral-4B-TTS-2603-mlx-4bit)
through the mlx-audio package — the native Apple Silicon path.

Setup:
    cd mac/voxtral
    uv venv
    uv pip install mlx-audio soundfile 'mistral-common[audio]'

Usage:
    python tts.py "Hello world" -o out.wav --voice casual_male
"""

import os
import subprocess
from pathlib import Path

VOXTRAL_DIR = Path(__file__).parent
VENV_PYTHON = VOXTRAL_DIR / ".venv" / "bin" / "python"

# Default Voxtral MLX checkpoint. 4-bit is fastest; swap to *-mlx-bf16 for
# higher quality at ~4x size.
DEFAULT_MODEL = os.environ.get(
    "WRIT_VOXTRAL_MODEL", "mlx-community/Voxtral-4B-TTS-2603-mlx-4bit"
)
DEFAULT_VOICE = "casual_male"

# Voxtral's built-in preset voices (English unless suffixed). Use voice cloning
# (pass a reference WAV path as --voice) to override.
VOICES = {
    "casual_male": "Casual male, English",
    "casual_female": "Casual female, English",
    "cheerful_female": "Cheerful female, English",
    "neutral_male": "Neutral male, English",
    "neutral_female": "Neutral female, English",
}


def setup_venv():
    """Create and set up the voxtral venv if it doesn't exist."""
    venv_dir = VOXTRAL_DIR / ".venv"
    if not venv_dir.exists():
        print("Setting up Voxtral venv...")
        subprocess.run(["uv", "venv"], cwd=VOXTRAL_DIR, check=True)
        subprocess.run(
            ["uv", "pip", "install", "mlx-audio", "soundfile", "mistral-common[audio]"],
            cwd=VOXTRAL_DIR,
            check=True,
        )
        print("Voxtral venv ready")
    return VENV_PYTHON.exists()


def render_speech(
    text: str,
    output_path: Path,
    voice: str = DEFAULT_VOICE,
    model_id: str = DEFAULT_MODEL,
    sample_rate: int = 24000,
) -> bool:
    """
    Render text to speech using Voxtral TTS via MLX.

    Args:
        text: The text to speak.
        output_path: Where to save the WAV file.
        voice: A preset voice id (e.g. "casual_male") OR a path to a reference
            WAV for voice cloning.
        model_id: HF model id (defaults to the 4-bit MLX checkpoint).
        sample_rate: Output WAV sample rate (Voxtral codec runs at 24 kHz).

    Returns:
        True if successful, False otherwise.
    """
    if not VENV_PYTHON.exists():
        if not setup_venv():
            print("Failed to set up Voxtral venv")
            return False

    # Subprocess runs with cwd=VOXTRAL_DIR; resolve so relative paths still work.
    output_path = Path(output_path).resolve()
    escaped_text = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    escaped_voice = voice.replace("\\", "\\\\").replace('"', '\\"')
    escaped_model = model_id.replace("\\", "\\\\").replace('"', '\\"')

    tts_script = f'''
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import soundfile as sf
from mlx_audio.tts.utils import load

model = load("{escaped_model}")

text = "{escaped_text}"
voice = "{escaped_voice}"

segments = []
for result in model.generate(text=text, voice=voice):
    segments.append(np.asarray(result.audio))

if not segments:
    raise RuntimeError("Voxtral produced no audio")

audio = segments[0] if len(segments) == 1 else np.concatenate(segments)
sf.write("{output_path}", audio, {sample_rate})
print("SUCCESS")
'''

    try:
        result = subprocess.run(
            [str(VENV_PYTHON), "-c", tts_script],
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(VOXTRAL_DIR),
        )
        if "SUCCESS" in result.stdout:
            return True
        print(f"Voxtral error: {result.stderr}")
        return False
    except subprocess.TimeoutExpired:
        print("Voxtral timed out")
        return False
    except Exception as e:
        print(f"TTS error: {e}")
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Voxtral TTS renderer (MLX)")
    parser.add_argument("text", help="Text to speak")
    parser.add_argument("-o", "--output", default="test.wav", help="Output WAV file")
    parser.add_argument(
        "-v", "--voice", default=DEFAULT_VOICE,
        help="Preset voice id (casual_male, casual_female, ...) or path to a reference WAV",
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL, help="HF model id (default: 4-bit MLX checkpoint)"
    )
    parser.add_argument("--list-voices", action="store_true", help="List built-in preset voices")
    args = parser.parse_args()

    if args.list_voices:
        print("Built-in preset voices (you can also pass a reference WAV path):")
        for vid, desc in VOICES.items():
            print(f"  {vid}: {desc}")
    else:
        success = render_speech(args.text, Path(args.output), voice=args.voice, model_id=args.model)
        print("Success!" if success else "Failed")
