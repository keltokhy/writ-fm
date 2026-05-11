#!/usr/bin/env python3
"""Station instance configuration for the WRIT radio runtime.

The codebase defaults to the original WRIT-FM single-station layout, but this
module lets the same runtime run multiple isolated stations at once by selecting
`WRIT_STATION_ID`.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "stations.yaml"
DEFAULT_STATION_ID = "writ-fm"


def _expand_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    expanded = os.path.expandvars(str(value))
    path = Path(expanded).expanduser()
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def _as_tuple(values: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    return tuple(str(v) for v in values or ())


@dataclass(frozen=True)
class AgentConfig:
    kind: str
    command: str
    args: tuple[str, ...] = ()


@dataclass(frozen=True)
class StreamConfig:
    icecast_host: str
    icecast_port: int
    mount: str
    api_port: int
    source_password: str
    stream_name: str
    stream_genre: str
    stream_description: str
    format: str = "Ogg"
    encoder: str = "oggenc-q4"

    @property
    def status_url(self) -> str:
        return f"http://{self.icecast_host}:{self.icecast_port}/status-json.xsl"


@dataclass(frozen=True)
class StationConfig:
    id: str
    call_sign: str
    agent: AgentConfig
    stream: StreamConfig
    output_dir: Path
    home_dir: Path
    schedule_path: Path
    public_now_playing_paths: tuple[Path, ...] = ()

    @property
    def runtime_dir(self) -> Path:
        return self.output_dir / "runtime"

    @property
    def ezstream_config_file(self) -> Path:
        return self.runtime_dir / "radio.xml"

    @property
    def playlist_file(self) -> Path:
        return self.runtime_dir / ".playlist.m3u"

    @property
    def silence_file(self) -> Path:
        return self.runtime_dir / ".silence.wav"

    @property
    def current_track_file(self) -> Path:
        return self.runtime_dir / ".current_track.txt"

    @property
    def now_playing_file(self) -> Path:
        return self.output_dir / "now_playing.json"

    @property
    def talk_dir(self) -> Path:
        return self.output_dir / "talk_segments"

    @property
    def bumper_dir(self) -> Path:
        return self.output_dir / "music_bumpers"

    @property
    def archive_dir(self) -> Path:
        return self.output_dir / "archive"

    @property
    def scripts_dir(self) -> Path:
        return self.output_dir / "scripts"

    @property
    def show_log_dir(self) -> Path:
        return self.output_dir / "show_logs"

    @property
    def intent_dir(self) -> Path:
        return self.output_dir / "operator_intents"

    @property
    def topic_bank_file(self) -> Path:
        return self.output_dir / "operator_topic_bank.json"

    @property
    def messages_file(self) -> Path:
        return self.home_dir / "messages.json"

    @property
    def ledger_path(self) -> Path:
        return self.home_dir / "station_ledger.jsonl"

    @property
    def active_threads_path(self) -> Path:
        return self.home_dir / "active_threads.json"

    @property
    def history_db_path(self) -> Path:
        return self.home_dir / "history.db"

    def env(self) -> dict[str, str]:
        return {
            "WRIT_STATION_ID": self.id,
            "WRIT_CALL_SIGN": self.call_sign,
            "WRIT_AGENT_KIND": self.agent.kind,
            "WRIT_AGENT_COMMAND": self.agent.command,
            "WRIT_OUTPUT_DIR": str(self.output_dir),
            "WRIT_RUNTIME_DIR": str(self.runtime_dir),
            "WRIT_STATION_HOME": str(self.home_dir),
            "WRIT_SCHEDULE_PATH": str(self.schedule_path),
            "WRIT_TALK_DIR": str(self.talk_dir),
            "WRIT_BUMPER_DIR": str(self.bumper_dir),
            "WRIT_ARCHIVE_DIR": str(self.archive_dir),
            "WRIT_SCRIPTS_DIR": str(self.scripts_dir),
            "WRIT_SHOW_LOG_DIR": str(self.show_log_dir),
            "WRIT_INTENT_DIR": str(self.intent_dir),
            "WRIT_TOPIC_BANK_FILE": str(self.topic_bank_file),
            "WRIT_PLAYLIST_FILE": str(self.playlist_file),
            "WRIT_SILENCE_FILE": str(self.silence_file),
            "WRIT_CURRENT_TRACK_FILE": str(self.current_track_file),
            "WRIT_NOW_PLAYING_FILE": str(self.now_playing_file),
            "WRIT_MESSAGES_FILE": str(self.messages_file),
            "WRIT_LEDGER_PATH": str(self.ledger_path),
            "WRIT_ACTIVE_THREADS_PATH": str(self.active_threads_path),
            "WRIT_HISTORY_DB_PATH": str(self.history_db_path),
            "WRIT_NOW_PLAYING_PORT": str(self.stream.api_port),
            "WRIT_ICECAST_HOST": self.stream.icecast_host,
            "WRIT_ICECAST_PORT": str(self.stream.icecast_port),
            "WRIT_ICECAST_MOUNT": self.stream.mount,
            "ICECAST_STATUS_URL": self.stream.status_url,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "call_sign": self.call_sign,
            "agent": {
                "kind": self.agent.kind,
                "command": self.agent.command,
                "args": list(self.agent.args),
            },
            "stream": {
                "icecast_host": self.stream.icecast_host,
                "icecast_port": self.stream.icecast_port,
                "mount": self.stream.mount,
                "api_port": self.stream.api_port,
                "stream_name": self.stream.stream_name,
                "stream_genre": self.stream.stream_genre,
                "stream_description": self.stream.stream_description,
                "format": self.stream.format,
                "encoder": self.stream.encoder,
            },
            "paths": {
                "output_dir": str(self.output_dir),
                "home_dir": str(self.home_dir),
                "schedule_path": str(self.schedule_path),
                "runtime_dir": str(self.runtime_dir),
                "playlist_file": str(self.playlist_file),
                "current_track_file": str(self.current_track_file),
                "now_playing_file": str(self.now_playing_file),
                "messages_file": str(self.messages_file),
                "ledger_path": str(self.ledger_path),
                "history_db_path": str(self.history_db_path),
                "topic_bank_file": str(self.topic_bank_file),
                "public_now_playing_paths": [str(p) for p in self.public_now_playing_paths],
            },
        }


def _built_in_config() -> dict[str, Any]:
    return {
        "default_station": DEFAULT_STATION_ID,
        "stations": {
            DEFAULT_STATION_ID: {
                "call_sign": "WRIT-FM",
                "agent": {"kind": "claude", "command": "claude"},
                "paths": {
                    "output_dir": "output",
                    "home_dir": "~/.writ",
                    "schedule_path": "config/schedule.yaml",
                },
                "stream": {
                    "mount": "/stream",
                    "api_port": 8001,
                    "stream_name": "WRIT-FM",
                    "stream_genre": "Talk Radio",
                    "stream_description": "The frequency between frequencies",
                },
            }
        },
    }


def load_config_file(path: Path = CONFIG_PATH) -> dict[str, Any]:
    if not path.exists():
        return _built_in_config()
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Station config must be a mapping: {path}")
    built_in = _built_in_config()
    data.setdefault("default_station", built_in["default_station"])
    data.setdefault("stations", built_in["stations"])
    return data


def station_ids(path: Path = CONFIG_PATH) -> list[str]:
    data = load_config_file(path)
    return list((data.get("stations") or {}).keys())


def load_station_config(station_id: str | None = None, path: Path = CONFIG_PATH) -> StationConfig:
    data = load_config_file(path)
    selected = station_id or os.environ.get("WRIT_STATION_ID") or data.get("default_station") or DEFAULT_STATION_ID
    stations = data.get("stations") or {}
    if selected not in stations:
        valid = ", ".join(stations)
        raise KeyError(f"Unknown station '{selected}'. Valid stations: {valid}")

    raw = stations[selected] or {}
    paths = raw.get("paths") or {}
    stream = raw.get("stream") or {}
    agent = raw.get("agent") or {}

    output_default = "output" if selected == DEFAULT_STATION_ID else f"output/stations/{selected}"
    home_default = "~/.writ" if selected == DEFAULT_STATION_ID else f"~/.writ/stations/{selected}"

    source_password = ""
    source_env = stream.get("source_password_env")
    if source_env:
        source_password = os.environ.get(str(source_env), "")
    source_password = source_password or str(stream.get("source_password", "writ_source_2024"))

    public_paths = tuple(
        p for p in (_expand_path(value) for value in paths.get("public_now_playing_paths", []))
        if p is not None
    )

    return StationConfig(
        id=selected,
        call_sign=str(raw.get("call_sign", selected.upper())),
        agent=AgentConfig(
            kind=str(agent.get("kind", "claude")).lower(),
            command=str(agent.get("command", agent.get("kind", "claude"))),
            args=_as_tuple(agent.get("args")),
        ),
        stream=StreamConfig(
            icecast_host=str(stream.get("icecast_host", "localhost")),
            icecast_port=int(stream.get("icecast_port", 8000)),
            mount=str(stream.get("mount", f"/{selected}")),
            api_port=int(stream.get("api_port", 8001)),
            source_password=source_password,
            stream_name=str(stream.get("stream_name", raw.get("call_sign", selected.upper()))),
            stream_genre=str(stream.get("stream_genre", "Talk Radio")),
            stream_description=str(stream.get("stream_description", "Autonomous AI radio")),
            format=str(stream.get("format", "Ogg")),
            encoder=str(stream.get("encoder", "oggenc-q4")),
        ),
        output_dir=_expand_path(paths.get("output_dir", output_default)) or PROJECT_ROOT / output_default,
        home_dir=_expand_path(paths.get("home_dir", home_default)) or Path.home() / ".writ",
        schedule_path=_expand_path(paths.get("schedule_path", "config/schedule.yaml")) or PROJECT_ROOT / "config" / "schedule.yaml",
        public_now_playing_paths=public_paths,
    )


def apply_station_env(station: StationConfig | None = None) -> dict[str, str]:
    selected = station or load_station_config()
    env = os.environ.copy()
    env.update(selected.env())
    return env


def get_field(station: StationConfig, field: str) -> Any:
    value: Any = station
    for part in field.split("."):
        value = getattr(value, part)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve WRIT station configuration")
    parser.add_argument("--station", help="Station id (defaults to WRIT_STATION_ID/default_station)")
    parser.add_argument("--json", action="store_true", help="Print resolved config as JSON")
    parser.add_argument("--env", action="store_true", help="Print shell export lines for this station")
    parser.add_argument("--ids", action="store_true", help="Print configured station ids")
    parser.add_argument("--field", help="Print a single resolved field, e.g. stream.api_port")
    args = parser.parse_args()

    if args.ids:
        print("\n".join(station_ids()))
        return 0

    station = load_station_config(args.station)
    if args.env:
        for key, value in station.env().items():
            print(f"export {key}={shlex.quote(value)}")
        return 0
    if args.field:
        value = get_field(station, args.field)
        print(value)
        return 0
    if args.json:
        print(json.dumps(station.to_dict(), indent=2))
        return 0

    print(station.id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
