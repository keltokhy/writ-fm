#!/usr/bin/env python3
"""
Shared helpers for WRIT-FM content generators.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "mac"))
from station_config import load_station_config  # noqa: E402

STATION = load_station_config()

DEFAULT_NEWS_FEEDS = (
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://feeds.npr.org/1001/rss.xml",
)
NEWS_CACHE_TTL_SECONDS = int(os.environ.get("WRIT_NEWS_CACHE_TTL", "600"))
NEWS_TIMEOUT_SECONDS = int(os.environ.get("WRIT_NEWS_TIMEOUT", "6"))

_NEWS_CACHE: dict[str, object] = {"timestamp": 0.0, "items": []}


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def get_time_of_day(hour: int | None = None, profile: str = "default") -> str:
    if hour is None:
        hour = datetime.now().hour

    if profile == "extended":
        if 6 <= hour < 10:
            return "morning"
        if 10 <= hour < 14:
            return "daytime"
        if 14 <= hour < 15:
            return "early_afternoon"
        if 15 <= hour < 18:
            return "afternoon"
        if 18 <= hour < 24:
            return "evening"
        return "late_night"

    if 6 <= hour < 10:
        return "morning"
    if 10 <= hour < 18:
        return "daytime"
    if 18 <= hour < 24:
        return "evening"
    return "late_night"


def preprocess_for_tts(text: str, *, include_cough: bool = True) -> str:
    text = text.replace("[pause]", "...")
    text = text.replace("[chuckle]", "heh...")
    if include_cough:
        text = text.replace("[cough]", "ahem...")
    text = text.replace('"', "")
    return text.strip()


def clean_claude_output(text: str, *, strip_quotes: bool = True) -> str:
    cleaned = text.replace("*", "").replace("_", "").strip()
    if strip_quotes and cleaned.startswith('"') and cleaned.endswith('"'):
        cleaned = cleaned[1:-1].strip()
    return cleaned


def run_claude(
    prompt: str,
    *,
    timeout: int = 60,
    model: str | None = None,
    min_length: int = 0,
    strip_quotes: bool = True,
) -> str | None:
    if STATION.agent.kind == "codex":
        args = [
            STATION.agent.command,
            "exec",
            "-C",
            str(PROJECT_ROOT),
            "-s",
            "danger-full-access",
            "--color",
            "never",
            "--ephemeral",
        ]
        if model:
            args.extend(["--model", model])
        args.append(prompt)
    else:
        args = [STATION.agent.command, *STATION.agent.args, "-p", prompt]
        if model:
            args.extend(["--model", model])

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        log(f"{STATION.agent.kind} timed out")
        return None
    except Exception as exc:
        log(f"{STATION.agent.kind} error: {exc}")
        return None

    if result.returncode != 0:
        stderr = result.stderr.strip().splitlines()
        if stderr:
            log(f"{STATION.agent.kind} failed: {stderr[-1]}")
        return None

    if not result.stdout.strip():
        return None

    script = clean_claude_output(result.stdout, strip_quotes=strip_quotes)
    if len(script) <= min_length:
        return None
    return script


def _strip_namespace(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _find_child_text(elem: ET.Element, name: str) -> str:
    for child in elem:
        if _strip_namespace(child.tag) == name and child.text:
            return child.text.strip()
    return ""


def _extract_source_title(root: ET.Element, fallback: str) -> str:
    tag = _strip_namespace(root.tag)
    if tag == "rss":
        for child in root:
            if _strip_namespace(child.tag) == "channel":
                title = _find_child_text(child, "title")
                return title or fallback
    if tag == "feed":
        title = _find_child_text(root, "title")
        return title or fallback
    return fallback


def _normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def fetch_headlines(max_items: int | None = None) -> list[dict]:
    now = time.time()
    cached_items = _NEWS_CACHE.get("items", [])
    if cached_items and now - float(_NEWS_CACHE.get("timestamp", 0.0)) < NEWS_CACHE_TTL_SECONDS:
        return list(cached_items)

    max_items = max_items or int(os.environ.get("WRIT_NEWS_MAX_ITEMS", "8"))
    feed_env = os.environ.get("WRIT_NEWS_FEEDS")
    feeds = [f.strip() for f in feed_env.split(",")] if feed_env else list(DEFAULT_NEWS_FEEDS)
    feeds = [f for f in feeds if f]

    headlines: list[dict] = []
    seen: set[str] = set()

    for feed_url in feeds:
        try:
            with urllib.request.urlopen(feed_url, timeout=NEWS_TIMEOUT_SECONDS) as response:
                content = response.read()
            root = ET.fromstring(content)
        except Exception:
            continue

        fallback = urllib.parse.urlparse(feed_url).netloc or "Unknown Source"
        source = _extract_source_title(root, fallback)

        for elem in root.iter():
            tag = _strip_namespace(elem.tag)
            if tag not in ("item", "entry"):
                continue
            title = _find_child_text(elem, "title")
            if not title:
                continue
            norm = _normalize_title(title)
            if not norm or norm in seen:
                continue
            seen.add(norm)
            headlines.append({"title": title, "source": source})
            if len(headlines) >= max_items:
                break
        if len(headlines) >= max_items:
            break

    _NEWS_CACHE["timestamp"] = now
    _NEWS_CACHE["items"] = list(headlines)
    return headlines


def format_headlines(headlines: list[dict], max_items: int | None = None) -> str:
    if not headlines:
        return ""
    max_items = max_items or len(headlines)
    lines = []
    for item in headlines[:max_items]:
        title = item.get("title", "").strip()
        source = item.get("source", "").strip() or "Source"
        if title:
            lines.append(f"- [{source}] {title}")
    return "\n".join(lines)


# =============================================================================
# SHARED TTS RENDERING
# =============================================================================

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_KOKORO_DIR = _PROJECT_ROOT / "mac" / "kokoro"
_KOKORO_PYTHON = _KOKORO_DIR / ".venv" / "bin" / "python"
_CHATTERBOX_DIR = _PROJECT_ROOT / "mac" / "chatterbox"
_CHATTERBOX_PYTHON = _CHATTERBOX_DIR / ".venv" / "bin" / "python"
_VOXTRAL_DIR = _PROJECT_ROOT / "mac" / "voxtral"
_VOXTRAL_PYTHON = _VOXTRAL_DIR / ".venv" / "bin" / "python"

_SUPPORTED_ENGINES = ("kokoro", "chatterbox", "voxtral")

_DEFAULT_ENGINE_VOICES = {
    "kokoro": "am_michael",
    "chatterbox": "",          # empty = Chatterbox built-in baseline voice
    "voxtral": "casual_male",
}


def resolve_engine(override: str | None = None) -> str:
    """Pick the TTS engine. Priority: explicit override > WRIT_TTS_ENGINE env > STATION.tts_engine > kokoro."""
    if override:
        return override.lower()
    env = os.environ.get("WRIT_TTS_ENGINE")
    if env:
        return env.strip().lower()
    station_engine = getattr(STATION, "tts_engine", None)
    if station_engine:
        return str(station_engine).lower()
    return "kokoro"


def resolve_voice(voice: str | dict | None, engine: str) -> str:
    """Resolve a voice spec to the per-engine voice id/path.

    Accepts:
      - str: legacy single-voice spec (treated as Kokoro voice for back-compat;
        passed through unchanged for the active engine if it's kokoro).
      - dict: {"kokoro": "...", "chatterbox": "...", "voxtral": "..."} — pick by engine.
      - None: fall back to engine's built-in default.
    """
    if voice is None:
        return _DEFAULT_ENGINE_VOICES.get(engine, "")
    if isinstance(voice, dict):
        if engine in voice and voice[engine] is not None:
            return str(voice[engine])
        return _DEFAULT_ENGINE_VOICES.get(engine, "")
    # Plain string — assume legacy Kokoro voice id.
    if engine == "kokoro":
        return str(voice)
    return _DEFAULT_ENGINE_VOICES.get(engine, "")


def get_audio_duration(filepath: Path) -> float | None:
    """Get audio duration in seconds via ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(filepath)],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception:
        pass
    return None


def render_kokoro(text: str, output_path: Path, voice: str = "am_michael") -> bool:
    """Render text to speech using Kokoro TTS."""
    if not _KOKORO_PYTHON.exists():
        log("Kokoro venv not found")
        return False

    # Subprocess runs with cwd=_KOKORO_DIR; resolve so relative paths still work.
    output_path = Path(output_path).resolve()
    escaped_text = text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ')

    tts_script = f'''
import warnings
warnings.filterwarnings("ignore")

from kokoro import KPipeline
import soundfile as sf
import numpy as np

pipe = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")

text = "{escaped_text}"
voice = "{voice}"

generator = pipe(text, voice=voice, speed=1.0)
audio_segments = []
for _, _, audio in generator:
    audio_segments.append(audio)

if len(audio_segments) == 1:
    full_audio = audio_segments[0]
else:
    full_audio = np.concatenate(audio_segments)

sf.write("{output_path}", full_audio, 24000)
print("SUCCESS")
'''

    try:
        result = subprocess.run(
            [str(_KOKORO_PYTHON), "-c", tts_script],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(_KOKORO_DIR),
        )
        return "SUCCESS" in result.stdout
    except Exception as e:
        log(f"Kokoro error: {e}")
        return False


def render_chatterbox(
    text: str,
    output_path: Path,
    voice: str = "",
    exaggeration: float = 0.5,
    cfg_weight: float = 0.5,
) -> bool:
    """Render text to speech using Resemble AI's Chatterbox.

    voice is either an empty string (Chatterbox baseline voice) or a path to
    a short reference WAV for voice cloning.
    """
    if not _CHATTERBOX_PYTHON.exists():
        log("Chatterbox venv not found — run: cd mac/chatterbox && uv venv && uv pip install chatterbox-tts soundfile torch torchaudio 'setuptools<81'")
        return False

    output_path = Path(output_path).resolve()
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
            [str(_CHATTERBOX_PYTHON), "-c", tts_script],
            capture_output=True,
            text=True,
            timeout=900,
            cwd=str(_CHATTERBOX_DIR),
        )
        if "SUCCESS" in result.stdout:
            return True
        log(f"Chatterbox failed: {result.stderr.strip().splitlines()[-1] if result.stderr.strip() else 'no stderr'}")
        return False
    except Exception as e:
        log(f"Chatterbox error: {e}")
        return False


def render_voxtral(
    text: str,
    output_path: Path,
    voice: str = "casual_male",
    model_id: str | None = None,
    sample_rate: int = 24000,
) -> bool:
    """Render text to speech using Mistral's Voxtral-4B-TTS via mlx-audio.

    voice is either a preset id (casual_male, casual_female, neutral_male, ...)
    or a path to a reference WAV for voice cloning.
    """
    if not _VOXTRAL_PYTHON.exists():
        log("Voxtral venv not found — run: cd mac/voxtral && uv venv && uv pip install mlx-audio soundfile 'mistral-common[audio]'")
        return False

    chosen_model = model_id or os.environ.get(
        "WRIT_VOXTRAL_MODEL", "mlx-community/Voxtral-4B-TTS-2603-mlx-4bit"
    )

    output_path = Path(output_path).resolve()
    escaped_text = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    escaped_voice = voice.replace("\\", "\\\\").replace('"', '\\"')
    escaped_model = chosen_model.replace("\\", "\\\\").replace('"', '\\"')

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
            [str(_VOXTRAL_PYTHON), "-c", tts_script],
            capture_output=True,
            text=True,
            timeout=900,
            cwd=str(_VOXTRAL_DIR),
        )
        if "SUCCESS" in result.stdout:
            return True
        log(f"Voxtral failed: {result.stderr.strip().splitlines()[-1] if result.stderr.strip() else 'no stderr'}")
        return False
    except Exception as e:
        log(f"Voxtral error: {e}")
        return False


def render_speech(
    text: str,
    output_path: Path,
    voice: str | dict | None = None,
    *,
    engine: str | None = None,
) -> bool:
    """Dispatch a TTS render to the active engine.

    Args:
        text: Text to speak.
        output_path: Destination WAV.
        voice: Either a single voice id/path (legacy) or a dict mapping
            engine name -> voice id/path. None falls back to the engine default.
        engine: Optional explicit engine override (else resolved from
            WRIT_TTS_ENGINE env / station config / "kokoro").
    """
    eng = resolve_engine(engine)
    if eng not in _SUPPORTED_ENGINES:
        log(f"Unknown TTS engine '{eng}' — falling back to kokoro")
        eng = "kokoro"
    resolved_voice = resolve_voice(voice, eng)

    if eng == "kokoro":
        return render_kokoro(text, output_path, resolved_voice or "am_michael")
    if eng == "chatterbox":
        return render_chatterbox(text, output_path, resolved_voice)
    if eng == "voxtral":
        return render_voxtral(text, output_path, resolved_voice or "casual_male")
    return False


def concatenate_audio(chunk_files: list[Path], output_path: Path, gap_seconds: float = 0) -> bool:
    """Concatenate WAV files, optionally with silence gaps between them."""
    if len(chunk_files) == 1:
        shutil.move(str(chunk_files[0]), str(output_path))
        return True

    list_file = output_path.with_suffix('.concat.txt')

    try:
        with open(list_file, 'w') as f:
            for cf in chunk_files:
                f.write(f"file '{cf}'\n")

        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-ar", "24000", "-ac", "1",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, timeout=120)

        list_file.unlink(missing_ok=True)
        for cf in chunk_files:
            cf.unlink(missing_ok=True)

        if result.returncode != 0:
            stderr = result.stderr.decode()
            stdout = result.stdout.decode()
            log(f"  Concat failed (rc={result.returncode}):")
            log(f"  STDERR (last 1500): {stderr[-1500:]}")
            if stdout.strip():
                log(f"  STDOUT: {stdout[-500:]}")
            return False

        return output_path.exists()

    except Exception as e:
        log(f"  Concat error: {e}")
        list_file.unlink(missing_ok=True)
        return False


def render_single_voice(text: str, output_path: Path, voice: str | dict | None) -> bool:
    """Render a single-voice script to audio, chunking for long content.

    Dispatches through render_speech to the configured TTS engine. `voice` can
    be a legacy string (Kokoro voice) or a per-engine dict.
    """
    MAX_CHUNK_WORDS = 100
    words = text.split()
    engine = resolve_engine()

    if len(words) <= MAX_CHUNK_WORDS:
        return render_speech(text, output_path, voice, engine=engine)

    sentences = re.split(r'(?<=[.!?])\s+', text)

    chunks: list[str] = []
    current_chunk: list[str] = []
    current_words = 0

    for sentence in sentences:
        sentence_words = len(sentence.split())
        if current_words + sentence_words > MAX_CHUNK_WORDS and current_chunk:
            chunks.append(' '.join(current_chunk))
            current_chunk = [sentence]
            current_words = sentence_words
        else:
            current_chunk.append(sentence)
            current_words += sentence_words

    if current_chunk:
        chunks.append(' '.join(current_chunk))

    log(f"  Rendering {len(chunks)} chunks via {engine} (voice: {resolve_voice(voice, engine)})...")

    import tempfile
    tmp_dir = Path(tempfile.mkdtemp(prefix="writ_chunks_"))

    chunk_files: list[Path] = []
    failed_chunks = 0
    for i, chunk in enumerate(chunks):
        chunk_path = tmp_dir / f"chunk{i:03d}.wav"
        for attempt in range(2):
            if render_speech(chunk, chunk_path, voice, engine=engine):
                chunk_files.append(chunk_path)
                break
            time.sleep(2)
        else:
            failed_chunks += 1

    if failed_chunks:
        log(f"  {failed_chunks}/{len(chunks)} chunks failed to render")

    if not chunk_files:
        log("  No chunks rendered")
        tmp_dir.rmdir()
        return False

    result = concatenate_audio(chunk_files, output_path)
    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return result
