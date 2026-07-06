"""Export ForensicEvents to disk (JSONL / CSV, optional gzip)."""

from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path
from typing import Iterable

from mneme.ecs.schema import ForensicEvent

FORMATS = ("jsonl", "csv")

_CSV_COLUMNS = [
    "@timestamp", "event.action", "event.dataset",
    "process.pid", "process.parent_pid", "process.name", "process.command_line",
    "dll.name", "source.ip", "destination.ip", "message",
]


def _get(d: dict, dotted: str):
    cur = d
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    if isinstance(cur, list):
        return ";".join(str(x) for x in cur)
    return cur


def _open(path: Path, gz: bool):
    if gz:
        return gzip.open(path, "wt", encoding="utf-8", newline="")
    return open(path, "w", encoding="utf-8", newline="")


def export(events: Iterable[ForensicEvent], output: Path, fmt: str = "jsonl",
           gz: bool = False) -> int:
    if fmt not in FORMATS:
        raise ValueError(f"unknown format {fmt!r}; choose from {FORMATS}")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    if fmt == "jsonl":
        with _open(output, gz) as fh:
            for ev in events:
                fh.write(json.dumps(ev.to_ecs(), ensure_ascii=False, default=str))
                fh.write("\n")
                count += 1
    else:
        with _open(output, gz) as fh:
            writer = csv.DictWriter(fh, fieldnames=_CSV_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            for ev in events:
                d = ev.to_ecs()
                writer.writerow({c: _get(d, c) for c in _CSV_COLUMNS})
                count += 1
    return count
