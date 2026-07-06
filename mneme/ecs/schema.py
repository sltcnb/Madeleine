"""ECS v8 forensic event model for memory artifacts.

A pydantic-validated subset of Elastic Common Schema v8 covering the fields
Mneme parsers populate from Volatility3 output. Memory-specific data that
has no clean ECS home lives under the `memory` namespace as free-form dicts.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="allow")


class Event(_Base):
    action: Optional[str] = None
    category: list[str] = Field(default_factory=list)
    type: list[str] = Field(default_factory=list)
    outcome: Optional[str] = None
    kind: str = "event"
    dataset: Optional[str] = None  # e.g. "windows.pslist"
    module: str = "memory"


class Process(_Base):
    pid: Optional[int] = None
    parent_pid: Optional[int] = None
    name: Optional[str] = None
    command_line: Optional[str] = None
    executable: Optional[str] = None
    start: Optional[str] = None      # create time
    exit: Optional[str] = None       # exit time
    threads: Optional[int] = None
    entity_id: Optional[str] = None  # offset, stable per-dump id


class Dll(_Base):
    name: Optional[str] = None
    path: Optional[str] = None
    base: Optional[str] = None
    size: Optional[int] = None


class Network(_Base):
    transport: Optional[str] = None
    protocol: Optional[str] = None
    state: Optional[str] = None
    direction: Optional[str] = None


class Host(_Base):
    ip: Optional[str] = None
    port: Optional[int] = None


class Registry(_Base):
    hive: Optional[str] = None
    key: Optional[str] = None
    value: Optional[str] = None
    data: Optional[str] = None


class ForensicEvent(_Base):
    """One normalized memory event. Serialize with `.to_ecs()`."""

    timestamp: Optional[str] = Field(default=None, alias="@timestamp")
    event: Event = Field(default_factory=Event)
    process: Optional[Process] = None
    dll: Optional[Dll] = None
    network: Optional[Network] = None
    source: Optional[Host] = None
    destination: Optional[Host] = None
    registry: Optional[Registry] = None
    message: Optional[str] = None
    host: Optional[dict[str, Any]] = None
    # Memory-specific raw + threat namespaces.
    memory: Optional[dict[str, Any]] = None
    threat: Optional[dict[str, Any]] = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    def to_ecs(self) -> dict[str, Any]:
        raw = self.model_dump(by_alias=True, exclude_none=True)
        return _prune(raw)


def _prune(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            pv = _prune(v)
            if pv in (None, {}, []):
                continue
            out[k] = pv
        return out
    if isinstance(obj, list):
        return [_prune(v) for v in obj]
    return obj
