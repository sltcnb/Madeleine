# Contributing to Madeleine

Thanks for helping improve Madeleine. This guide covers the essentials.

## Development setup

```bash
git clone https://github.com/sltcnb/Madeleine
cd Madeleine
python -m venv .venv && source .venv/bin/activate
pip install -e ".[web,dev]"      # add ".[vol]" for the `run` stage
pre-commit install               # lint/format on commit
```

## Tests and linting

```bash
pytest -q          # unit tests — no memory dump required
ruff check .       # lint
ruff format .      # format
```

The unit suite runs entirely on the JSON fixtures in `tests/fixtures/`, so no
Volatility3 install or memory image is needed. End-to-end tests are opt-in:

```bash
MNEME_TEST_DUMP=/path/to/mem.raw pytest -m integration
```

Please keep the suite green and add tests for new parsers, detections, or
exporters.

## Adding a parser

Register a mapper in `mneme/core/parser.py` with `@register("<plugin.name>")`
and return a `ForensicEvent`. Use `_pick()` for column-name tolerance and stow
the untouched row under `memory.raw`. Add a fixture under `tests/fixtures/` and
a test in `tests/unit/test_parser.py`.

## Commit style

Use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`,
`fix:`, `docs:`, `chore:`, …). Keep commits focused and the subject under
~50 characters.

## Pull requests

- Branch off `main`.
- Ensure `ruff check .` and `pytest -q` pass locally.
- Describe the motivation and any behavioral change.
- One logical change per PR where practical.

## Reporting security issues

See [SECURITY.md](SECURITY.md) — do not file public issues for vulnerabilities.
