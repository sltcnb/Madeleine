"""Timeline reconstruction from normalized memory events.

Pulls timestamped events (process create/exit, network connections, DLL loads,
registry) into one ordered stream, assigns a severity, and clusters events that
fall inside a short window so bursts of activity read as one incident.
"""

from __future__ import annotations

from typing import Any, Iterable

Event = dict[str, Any]

_SEVERITY_BY_ACTION = {
    "process_create": "info",
    "process_exit": "info",
    "dll_load": "low",
    "network_connection": "medium",
    "suspicious_memory": "high",
    "registry_hive": "low",
    "service": "medium",
}


def _get(ev: Event, dotted: str, default=None):
    cur: Any = ev
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return default
        cur = cur.get(part)
        if cur is None:
            return default
    return cur


def build(events: Iterable[Event]) -> list[dict]:
    """Ordered timeline of timestamped events (undated dropped)."""
    out = []
    for ev in events:
        ts = ev.get("@timestamp")
        if not ts:
            continue
        action = _get(ev, "event.action", "event")
        out.append({
            "@timestamp": ts,
            "action": action,
            "severity": _SEVERITY_BY_ACTION.get(action, "info"),
            "pid": _get(ev, "process.pid"),
            "process": _get(ev, "process.name"),
            "description": ev.get("message") or action,
        })
    out.sort(key=lambda e: e["@timestamp"])
    return out


def cluster(timeline: list[dict], window_seconds: int = 1) -> list[dict]:
    """Group adjacent events sharing a truncated-timestamp bucket.

    Cheap, timezone-agnostic clustering on the ISO string prefix: whole-second
    windows compare the first 19 chars ('YYYY-MM-DDTHH:MM:SS'); minute windows
    the first 16. Good enough for reconstruction without parsing every format.
    """
    if not timeline:
        return []
    prefix = 19 if window_seconds <= 1 else 16
    clusters: list[dict] = []
    cur_key = None
    for ev in timeline:
        key = str(ev["@timestamp"])[:prefix]
        if key != cur_key:
            clusters.append({"window": key, "events": [], "max_severity": "info"})
            cur_key = key
        c = clusters[-1]
        c["events"].append(ev)
        if _rank(ev["severity"]) > _rank(c["max_severity"]):
            c["max_severity"] = ev["severity"]
    return clusters


def _rank(sev: str) -> int:
    return {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}.get(sev, 0)
