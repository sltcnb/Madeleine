# Mneme — Usage Guide

Complete guide to every command, flag, and workflow. For a 60-second overview
see the [README](../README.md); for deployment see [deployment.md](deployment.md).

---

## Table of contents

1. [Install](#install)
2. [Mental model](#mental-model)
3. [The commands](#the-commands)
   - [run](#run) · [parse](#parse) · [detect](#detect) · [timeline](#timeline)
   - [report](#report) · [export](#export) · [stix](#stix)
   - [plugins](#plugins) · [parsers](#parsers) · [serve](#serve)
4. [End-to-end walkthrough](#end-to-end-walkthrough)
5. [Working without a dump](#working-without-a-dump)
6. [Web API](#web-api)
7. [Acquiring memory (Talon & friends)](#acquiring-memory-talon--friends)
8. [Troubleshooting](#troubleshooting)

---

## Install

```bash
python -m venv .venv && . .venv/bin/activate

pip install -e ".[vol]"          # + Volatility3   (needed only for `run`)
pip install -e ".[web]"          # + FastAPI/uvicorn (needed only for `serve`)
pip install -e ".[yara]"         # + yara-python   (needed only for YARA scans)
pip install -e ".[vol,web,dev]"  # everything + test deps
```

Verify:

```bash
mneme --version
mneme --help
```

Volatility3, FastAPI and YARA are all **optional**. Without them the analysis
pipeline (`parse`/`detect`/`timeline`/`report`/`export`/`stix`) still runs on
pre-collected Volatility3 JSON.

---

## Mental model

A **case** is a directory. Mneme fills it in stages and never mixes raw
evidence with derived data:

```
case/
├── raw/                       # verbatim Volatility3 JSON, one file per plugin
│   ├── windows.pslist.json
│   ├── windows.malfind.json
│   └── …
├── ecs/                       # normalized ECS v8 events, one file per dataset
│   ├── windows.pslist.ecs.jsonl
│   └── …
└── report.html               # rendered on demand
```

Data flows one way:

```
 dump.raw ──run──▶ case/raw ──parse──▶ case/ecs ──▶ detect
                                              │
                                              ├──▶ timeline
                                              ├──▶ report
                                              ├──▶ export (jsonl/csv)
                                              └──▶ stix
```

Only `run` touches the dump and needs Volatility3. Everything downstream reads
`case/ecs`, so you can hand a colleague just the ECS files and they get the same
detections.

---

## The commands

Global: `mneme [COMMAND] --help` prints per-command help.

### run

Execute Volatility3 plugins against a memory dump into `case/raw/`.

```bash
mneme run DUMP -o CASE_DIR [options]
```

| Flag | Default | Meaning |
|------|---------|---------|
| `-o, --output` | *(required)* | Case dir; `raw/` created inside |
| `--os {windows,linux,mac}` | inferred | Force OS profile (default: guess from dump filename) |
| `--plugin NAME` | — | Run only these plugins (repeatable); skips the recommended set |
| `--vol-bin PATH` | `vol` | Volatility3 binary to invoke |
| `--workers N` | `4` | Concurrency for parallel-safe plugins |

Behavior:

- Auto-detects OS, then runs the **recommended plugin set** for it
  (`mneme plugins --os windows` to preview).
- Parallel-safe plugins (pslist, netscan, malfind, …) run concurrently; ordering
  plugins run first.
- Results are **cached** by `sha256(dump) + plugin + args` — re-running is
  instant and safe.
- One failing plugin never aborts the triage; failures are reported and skipped.

```bash
# full recommended triage, auto OS
mneme run memory.raw -o case/

# force Linux, 8 workers
mneme run vmcore -o case/ --os linux --workers 8

# just two plugins
mneme run mem.raw -o case/ --plugin windows.malfind --plugin windows.netscan

# custom Vol3 binary
mneme run mem.raw -o case/ --vol-bin /opt/vol3/vol
```

### parse

Normalize raw Vol3 JSON → ECS v8 events in `case/ecs/`.

```bash
mneme parse RAW_DIR -o CASE_DIR
```

Reads every `*.json` in `RAW_DIR`, infers the dataset from the filename stem
(cache digests like `windows.pslist.ab12cd34.json` are stripped), dispatches to
the matching parser, and writes `<dataset>.ecs.jsonl`. Files with no parser or
bad JSON are skipped with a warning.

### detect

Run malware-detection heuristics over normalized events.

```bash
mneme detect ECS_INPUT [--yara RULES] [--json]
```

| Flag | Meaning |
|------|---------|
| `--yara PATH` | YARA rules file (source or compiled); scans malfind regions |
| `--json` | Emit raw JSON instead of a table |

`ECS_INPUT` is a `case/ecs` directory (all `*.ecs.jsonl` loaded) or a single
file. Findings are ranked by severity then confidence; findings sharing a PID
reinforce each other's confidence (correlation bump).

Detections (each MITRE ATT&CK-mapped):

| Type | Technique | ATT&CK |
|------|-----------|--------|
| process_injection | RWX private memory | T1055 |
| process_hollowing | anomalous parent | T1055.012 |
| dkom | hidden process (scan ∖ list) | T1014 |
| rootkit | hooked syscall/SSDT/IDT | T1014 |
| persistence | service → LOLBin / temp path | T1543.003 |
| credential_theft | lsass injection / access | T1003.001 |
| yara_match | rule hit on malfind | — |

```bash
mneme detect case/ecs
mneme detect case/ecs --yara rules/malware.yar
mneme detect case/ecs --json | jq '.[] | select(.severity=="critical")'
```

### timeline

Build an ordered timeline; optionally cluster bursts.

```bash
mneme timeline ECS_INPUT [--cluster] [--json] [--limit N]
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--cluster` | off | Group events into 1-second windows |
| `--json` | off | Raw JSON output |
| `--limit N` | `50` | Rows to show in table mode |

```bash
mneme timeline case/ecs --limit 100
mneme timeline case/ecs --cluster
mneme timeline case/ecs --json > timeline.json
```

### report

Render a self-contained HTML report (summary cards, ranked findings, IOCs,
timeline). No external assets — open offline or embed in a wiki.

```bash
mneme report CASE_DIR [--os OS] [-o OUTPUT]
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--os` | `windows` | OS label shown in the header |
| `-o, --output` | `CASE_DIR/report.html` | Report path |

```bash
mneme report case/
mneme report case/ --os linux -o /srv/reports/case42.html
```

### export

Convert normalized events to JSONL or CSV, optionally gzipped.

```bash
mneme export ECS_INPUT -o OUTPUT [--format {jsonl,csv}] [--gzip]
```

```bash
mneme export case/ecs -o events.jsonl
mneme export case/ecs -o events.csv --format csv
mneme export case/ecs -o events.jsonl.gz --gzip
```

### stix

Extract IOCs (routable IPs, domains, file paths) and emit a STIX 2.1 bundle.

```bash
mneme stix ECS_INPUT [-o OUTPUT]      # stdout if -o omitted
```

```bash
mneme stix case/ecs -o iocs.stix.json
mneme stix case/ecs | jq '.objects | length'
```

### plugins

List the recommended plugin set for an OS.

```bash
mneme plugins --os {windows,linux,mac}
```

### parsers

List datasets that have a registered parser.

```bash
mneme parsers
```

### serve

Launch the web GUI + JSON API (needs `[web]`).

```bash
mneme serve [--host 0.0.0.0] [--port 8080]
```

---

## End-to-end walkthrough

```bash
# 0. env
python -m venv .venv && . .venv/bin/activate && pip install -e ".[vol]"

# 1. acquire (see Talon section) → memory.raw

# 2. run Volatility3 triage
mneme run memory.raw -o case/

# 3. normalize
mneme parse case/raw -o case/

# 4. triage findings
mneme detect   case/ecs
mneme timeline case/ecs --cluster

# 5. deliverables
mneme report case/                 # → case/report.html
mneme stix   case/ecs -o iocs.json
mneme export case/ecs -o events.csv --format csv
```

---

## Working without a dump

No Volatility3? No dump on this host? Produce Vol3 JSON anywhere and analyze it
with Mneme. File names must be `<plugin>.json`:

```bash
# on the box that has Vol3 + the dump
for p in windows.pslist windows.pstree windows.malfind windows.netscan \
         windows.cmdline windows.svcscan; do
  vol -r json -f mem.raw "$p" > "case/raw/$p.json"
done

# anywhere (offline, no Vol3)
mneme parse  case/raw -o case/
mneme detect case/ecs
mneme report case/
```

This is exactly how the test suite runs — see `tests/fixtures/`.

---

## Web API

Start with `mneme serve` (or Docker). Dashboard at `/`, API under `/api`.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/cases` | List cases |
| POST | `/api/cases/{name}/raw?dataset=X` | Upload a raw Vol3 JSON file (auto-parsed) |
| GET | `/api/cases/{name}/detections` | Findings JSON |
| GET | `/api/cases/{name}/timeline?cluster=true` | Timeline JSON |
| GET | `/api/cases/{name}/iocs` | Extracted IOCs |
| GET | `/api/cases/{name}/report?os_type=windows` | HTML report |
| GET | `/healthz` | Liveness |

```bash
curl -F file=@case/raw/windows.pslist.json \
  "http://localhost:8080/api/cases/demo/raw?dataset=windows.pslist"
curl http://localhost:8080/api/cases/demo/detections | jq .
```

Cases persist under `MNEME_DATA` (default `/data`). Case names are validated
to a single path segment (no traversal).

---

## Acquiring memory with Talon

Mneme **analyzes** memory; it does not acquire it. **Talon** — the Citadel
suite's acquisition agent (first node of the pipeline) — does the acquisition.
Talon writes an *artifact bundle*; its `memory` category produces exactly the
raw image Mneme consumes. They chain directly:

```
Talon ──bundle(memory/*.dmp)──▶ Mneme run ──▶ parse ──▶ detect/report
```

### How Talon produces a dump

Memory is a **Heavy / Opt-in** category — never in Talon's defaults (dumps are
4–64 GB), so request it explicitly. Per-OS engine:

| OS | Engine | Bundle path | Format |
|----|--------|-------------|--------|
| Windows | WinPmem (`winpmem_mini_x64_rc2.exe` beside the collector) | `memory/memory-<HOST>-<TS>.dmp` | raw |
| Linux | avml (fallback `/dev/fmem`), root | `memory/memory-<HOST>-<TS>.lime` / `.raw` | LiME / raw |
| macOS | osxpmem, root | `memory/memory-<HOST>-<TS>…` | AFF4 |

Volatility3 reads all three natively, so every one feeds `mneme run`
unchanged. Talon also has a `memory_artifacts` category (dead-box `pagefile.sys`,
`hiberfil.sys`, `swapfile.sys` from a mounted volume).

### End-to-end: Talon → Mneme

```bash
# 1. ACQUIRE on the target (elevated). WinPmem must sit beside the collector.
talon --collect memory --output E:\evidence\host01.zip
#   → bundle: manifest.json | events.jsonl | memory/memory-host01-<ts>.dmp | bundle.sha256

# 2. EXTRACT the memory image on the analysis workstation
unzip E:\evidence\host01.zip -d host01_bundle
#   the dump is the file under memory/  (category "memory" in manifest.json)
DUMP=$(python3 - <<'PY'
import json,glob
m=json.load(open(glob.glob("host01_bundle/**/manifest.json",recursive=True)[0]))
print(next(a["name"] for a in m["artifacts"] if a["category"]=="memory"))
PY
)

# 3. ANALYZE with Mneme
mneme run   "host01_bundle/$DUMP" -o case_host01/
mneme parse case_host01/raw -o case_host01/
mneme detect case_host01/ecs
mneme report case_host01/
```

### Why the handoff is clean

- **Formats line up.** Talon's WinPmem `.dmp`, avml `.lime`, and osxpmem AFF4 are
  all Volatility3-native — no conversion.
- **Integrity carries through.** Talon's `manifest.json` records each artifact's
  `sha256`; Mneme keys its own result cache on `sha256(dump)`. Compare the
  two to prove the analyzed image is the acquired one.
- **Same case, both stages.** Both tools speak the Citadel suite: Talon uploads
  bundles to a case (`--api-url … --case-id IR-001`); Mneme emits ECS +
  STIX, ready to push to the same case.
- **Air-gapped split.** Acquire with Talon on the target, run `vol -r json` on a
  clean host, `mneme parse` offline — no dump ever leaves the enclave (see
  [Working without a dump](#working-without-a-dump)).

### Remote / fleet

Talon's gRPC agent (mTLS) collects `memory` across a fleet and lands bundles in
S3/MinIO. Pull a bundle, extract its `memory/` file, and point `mneme run`
at it — identical from step 2 onward.

### Caveats

- WinPmem is **not** bundled with Talon — drop `winpmem_mini_x64_rc2.exe` beside
  the collector (Talon prints a download URL if it's missing).
- Acquisition needs elevation (Administrator / root) and can take up to 2 h;
  Talon's per-dump timeout is 2 h.
- `hiberfil.sys` from `memory_artifacts` is compressed — decompress
  (e.g. `hibr2bin`) before `mneme run`; a live `.dmp`/`.lime`/AFF4 needs no
  such step.

---

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `'vol' not found` on `run` | Volatility3 missing → `pip install -e ".[vol]"` or pass `--vol-bin` |
| `no parser for 'X'` on `parse` | That plugin has no mapper yet; other files still parse. See `mneme parsers` |
| `web extras missing` on `serve` | `pip install -e ".[web]"` |
| YARA findings never appear | `pip install -e ".[yara]"` and pass `--yara rules.yar` |
| Empty detections | Confirm `case/ecs/*.ecs.jsonl` exist and are non-empty (`parse` ran) |
| `run` seems to hang | Large dumps are slow; each plugin has a 30-min timeout. Watch per-plugin progress lines |
| Externally-managed-environment pip error | Use a venv (`python -m venv .venv`) |
