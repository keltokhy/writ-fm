#!/usr/bin/env python3
"""Station-local operator topic bank.

Operators use this file-backed bank to grow each station's editorial surface
without editing code. The talk generator merges these station-local topics with
the built-in seed pools at selection time.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "mac"))
from station_config import load_station_config  # noqa: E402
from schedule import load_schedule  # noqa: E402

STATION = load_station_config()


def topic_bank_path(path: str | Path | None = None) -> Path:
    if path:
        return Path(path)
    env_path = os.environ.get("WRIT_TOPIC_BANK_FILE")
    return Path(env_path) if env_path else STATION.topic_bank_file


def _clean_topic(topic: Any) -> str:
    return " ".join(str(topic).strip().split())


def normalize_bank(data: Any) -> dict[str, list[str]]:
    if not isinstance(data, dict):
        return {}

    raw_topics = data.get("topics", data)
    if not isinstance(raw_topics, dict):
        return {}

    normalized: dict[str, list[str]] = {}
    for focus, topics in raw_topics.items():
        if not isinstance(focus, str) or not isinstance(topics, list):
            continue
        seen: set[str] = set()
        cleaned: list[str] = []
        for topic in topics:
            value = _clean_topic(topic)
            key = value.lower()
            if value and key not in seen:
                seen.add(key)
                cleaned.append(value)
        if cleaned:
            normalized[focus.strip()] = cleaned
    return normalized


def load_topic_bank(path: str | Path | None = None) -> dict[str, list[str]]:
    bank_path = topic_bank_path(path)
    if not bank_path.exists():
        return {}
    try:
        data = json.loads(bank_path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return normalize_bank(data)


def write_topic_bank(bank: dict[str, list[str]], path: str | Path | None = None) -> Path:
    bank_path = topic_bank_path(path)
    bank_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "station_id": STATION.id,
        "call_sign": STATION.call_sign,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "topics": normalize_bank(bank),
    }
    bank_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return bank_path


def merge_topic_pools(
    base_pools: dict[str, list[str]],
    path: str | Path | None = None,
) -> dict[str, list[str]]:
    merged = {focus: list(topics) for focus, topics in base_pools.items()}
    for focus, topics in load_topic_bank(path).items():
        existing = merged.setdefault(focus, [])
        seen = {topic.lower() for topic in existing}
        for topic in topics:
            key = topic.lower()
            if key not in seen:
                seen.add(key)
                existing.append(topic)
    return merged


def add_topics(focus: str, topics: Iterable[str], path: str | Path | None = None) -> tuple[Path, int]:
    cleaned_focus = focus.strip()
    if not cleaned_focus:
        raise ValueError("focus is required")

    bank = load_topic_bank(path)
    existing = bank.setdefault(cleaned_focus, [])
    seen = {topic.lower() for topic in existing}
    added = 0
    for topic in topics:
        value = _clean_topic(topic)
        key = value.lower()
        if value and key not in seen:
            seen.add(key)
            existing.append(value)
            added += 1
    return write_topic_bank(bank, path), added


def scheduled_focuses() -> list[str]:
    try:
        schedule = load_schedule(STATION.schedule_path)
    except Exception:
        return []
    return sorted({show.topic_focus for show in schedule.shows.values() if show.topic_focus})


def topic_bank_summary(
    focuses: Iterable[str] | None = None,
    path: str | Path | None = None,
) -> dict[str, Any]:
    bank = load_topic_bank(path)
    focus_list = list(focuses or scheduled_focuses())
    counts = {focus: len(bank.get(focus, [])) for focus in focus_list}
    extra = sorted(set(bank) - set(counts))
    for focus in extra:
        counts[focus] = len(bank.get(focus, []))
    return {
        "path": str(topic_bank_path(path)),
        "station_id": STATION.id,
        "call_sign": STATION.call_sign,
        "total": sum(len(topics) for topics in bank.values()),
        "counts": counts,
    }


def format_status(summary: dict[str, Any]) -> str:
    lines = [
        f"=== {summary.get('call_sign', STATION.call_sign)} Operator Topic Bank ===",
        f"Path: {summary['path']}",
        f"Total operator-added topics: {summary['total']}",
        "",
        "Scheduled focus counts:",
    ]
    for focus, count in summary["counts"].items():
        lines.append(f"- {focus}: {count}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage the station-local operator topic bank")
    parser.add_argument("--status", action="store_true", help="Show station-local topic-bank counts")
    parser.add_argument("--focus", help="Topic focus to edit, e.g. philosophy or open_issues")
    parser.add_argument("--add", action="append", default=[], help="Add a topic to --focus; repeatable")
    parser.add_argument("--path", help="Override topic bank path")
    parser.add_argument("--json", action="store_true", help="Print JSON status")
    args = parser.parse_args()

    if args.add:
        if not args.focus:
            parser.error("--focus is required with --add")
        path, added = add_topics(args.focus, args.add, args.path)
        print(f"Added {added} topic(s) to {args.focus}: {path}")

    if args.status or not args.add:
        summary = topic_bank_summary(path=args.path)
        if args.json:
            print(json.dumps(summary, indent=2, ensure_ascii=False))
        else:
            print(format_status(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
