# Security Policy

## Supported versions

Madeleine is pre-1.0; only the latest release on the `main` branch receives
security fixes.

| Version | Supported |
| ------- | --------- |
| latest  | yes       |
| older   | no        |

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Report vulnerabilities privately through GitHub's
[private vulnerability reporting](https://github.com/sltcnb/Madeleine/security/advisories/new).
Include:

- affected component (CLI, parser, web API, container image, …);
- reproduction steps or a proof of concept;
- impact assessment and any suggested remediation.

You can expect an acknowledgement within a few working days and a coordinated
disclosure once a fix is available.

## Operational notes

Madeleine processes untrusted forensic evidence (memory dumps and third-party
Volatility3 JSON). Handle it defensively:

- **Run in an isolated environment.** Analyze evidence in a container or VM,
  not on the acquisition host.
- **The web server is unauthenticated by design.** `mneme serve` binds
  `0.0.0.0` for container use and ships no auth. Put it behind a reverse proxy
  that enforces JWT/OAuth and RBAC, or bind it to `127.0.0.1` for local use.
  Never expose it directly to an untrusted network.
- **YARA rules are code.** Only load rule files you trust.
- **Raw evidence is preserved verbatim.** Treat the `raw/` and `ecs/`
  directories as sensitive; they can contain credentials, keys, and PII.
