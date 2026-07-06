"""Volatility3 orchestrator.

Wraps the `vol` CLI: builds commands with sane defaults, runs plugins (in
parallel where safe), caches results keyed by (dump-sha, plugin, args), and
writes raw plugin JSON to the case's raw/ directory. Raw evidence is preserved
verbatim; normalization happens later in parser.py.

Volatility3 itself is optional — if `vol` is absent, `run_plugin` raises a clear
error, but the rest of the pipeline (parse/detect/timeline) still works on any
pre-collected Vol3 JSON.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Optional

from mneme.core.plugins import PARALLEL_SAFE, detect_os, recommended


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


class VolatilityError(RuntimeError):
    pass


class Orchestrator:
    def __init__(self, dump_path: str, *, vol_bin: str = "vol",
                 raw_dir: Optional[Path] = None, workers: int = 4):
        self.dump_path = Path(dump_path)
        if not self.dump_path.exists():
            raise FileNotFoundError(self.dump_path)
        self.vol_bin = vol_bin
        self.raw_dir = Path(raw_dir) if raw_dir else self.dump_path.parent / "raw"
        self.workers = max(1, workers)
        self._sha: Optional[str] = None

    @property
    def dump_sha(self) -> str:
        if self._sha is None:
            self._sha = sha256_file(self.dump_path)
        return self._sha

    def _cache_path(self, plugin: str, args: Optional[dict]) -> Path:
        key = f"{self.dump_sha}:{plugin}:{json.dumps(args or {}, sort_keys=True)}"
        digest = hashlib.sha256(key.encode()).hexdigest()[:12]
        return self.raw_dir / f"{plugin}.{digest}.json"

    def _build_command(self, plugin: str, args: Optional[dict]) -> list[str]:
        cmd = [self.vol_bin, "-q", "-r", "json", "-f", str(self.dump_path), plugin]
        for k, v in (args or {}).items():
            cmd.append(f"--{k}")
            if v is not None and v is not True:
                cmd.append(str(v))
        return cmd

    def detect_os(self) -> str:
        """Cheap OS guess from the dump filename; refine with a banner scan."""
        return detect_os(self.dump_path.name)

    def run_plugin(self, plugin: str, args: Optional[dict] = None,
                   use_cache: bool = True, timeout: int = 1800) -> Path:
        """Run one plugin, write raw JSON to raw/, return that path."""
        if shutil.which(self.vol_bin) is None:
            raise VolatilityError(
                f"{self.vol_bin!r} not found — `pip install mneme-dfir[vol]`")
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        dest = self._cache_path(plugin, args)
        if use_cache and dest.exists():
            return dest
        cmd = self._build_command(plugin, args)
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if proc.returncode != 0:
            raise VolatilityError(f"{plugin} failed: {proc.stderr.strip()[:500]}")
        try:
            rows = json.loads(proc.stdout or "[]")
        except json.JSONDecodeError as e:
            raise VolatilityError(f"{plugin}: bad JSON from vol: {e}") from e
        dest.write_text(json.dumps(rows), encoding="utf-8")
        return dest

    def full_analysis(self, os_type: Optional[str] = None,
                      progress: Optional[Callable[[str, str], None]] = None,
                      ) -> dict[str, Any]:
        """Run the recommended plugin set; parallelize the safe ones.

        Returns {plugin: raw_json_path | {"error": msg}}.
        """
        os_type = os_type or self.detect_os()
        plugins = recommended(os_type)
        results: dict[str, Any] = {}
        parallel = [p for p in plugins if p in PARALLEL_SAFE]
        serial = [p for p in plugins if p not in PARALLEL_SAFE]

        def _one(p: str):
            if progress:
                progress(p, "start")
            try:
                path = self.run_plugin(p)
                if progress:
                    progress(p, "done")
                return p, path
            except Exception as e:  # noqa: BLE001 — one plugin must not kill triage
                if progress:
                    progress(p, "error")
                return p, {"error": str(e)}

        for p in serial:
            name, res = _one(p)
            results[name] = res
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futs = [pool.submit(_one, p) for p in parallel]
            for fut in as_completed(futs):
                name, res = fut.result()
                results[name] = res
        return results
