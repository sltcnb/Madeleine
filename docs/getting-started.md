# Getting Started

## Install

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[vol,dev]"     # vol = Volatility3, dev = tests
```

## Analyze a dump (full pipeline)

```bash
mneme run memory.raw -o case/     # Vol3 plugins → case/raw/
mneme parse case/raw -o case/     # → case/ecs/
mneme detect case/ecs             # ranked findings
mneme report case/                # → case/report.html
```

`run` auto-detects the OS from the dump name and runs the recommended plugin set
(`mneme plugins --os windows` to preview it). Parallel-safe plugins run
concurrently (`--workers N`); results are cached by dump SHA + plugin + args, so
re-runs are instant.

## Analyze pre-collected Vol3 JSON (no dump / no Volatility3)

Produce JSON yourself and drop it in `case/raw/` named `<plugin>.json`:

```bash
vol -r json -f mem.raw windows.pslist > case/raw/windows.pslist.json
mneme parse case/raw -o case/
mneme detect case/ecs
```

## Run a single plugin

```bash
mneme run mem.raw -o case/ --plugin windows.malfind --plugin windows.netscan
```

## Export

```bash
mneme export case/ecs -o events.csv  --format csv
mneme export case/ecs -o events.jsonl.gz --gzip
mneme stix   case/ecs -o iocs.stix.json
```
