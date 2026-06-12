# AI Projects Workspace

Multi-project workspace for product apps, automation pipelines, MCP servers, and shared tooling, maintained by [@biojuho](https://github.com/biojuho).

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](pyproject.toml)
[![Node 24](https://img.shields.io/badge/node-24-green.svg)](.nvmrc)
[![CodeQL](https://github.com/biojuho/BIOJUHO-Projects/actions/workflows/codeql.yml/badge.svg)](https://github.com/biojuho/BIOJUHO-Projects/actions/workflows/codeql.yml)

## What's inside

| Area | Path | Purpose |
| --- | --- | --- |
| Product apps | `apps/` | DeSci platform (BioLinker + frontend + contracts), AgriGuard, Dashboard |
| Automation | `automation/` | DailyNews, GetDayTrends, content-intelligence pipelines |
| MCP servers | `mcp/` | Model Context Protocol servers (Canva, GitHub, Notion, etc.) |
| Shared code | `packages/shared` | LLM clients, observability, telemetry, utilities |
| Ops | `ops/` | Scripts, monitoring (Grafana + Prometheus), nginx, smoke/healthcheck runners |
| Docs | `docs/` | Living docs and dated reports |
| Archive | `archive/` | Inactive or frozen material |
| Runtime | `var/` | Runtime data, logs, snapshots, generated smoke output |

## Quick start

```bash
git clone https://github.com/biojuho/BIOJUHO-Projects.git
cd BIOJUHO-Projects

cp .env.example .env
python bootstrap_legacy_paths.py     # creates compatibility aliases

# Workspace-wide smoke + health
python ops/scripts/run_workspace_smoke.py --scope all
python ops/scripts/healthcheck.py
```

See [`QUICK_START.md`](QUICK_START.md) for the full bootstrap walkthrough and per-project commands.

## Documentation map

- [`QUICK_START.md`](QUICK_START.md) — first-time setup, prerequisites, root commands
- [`CONTEXT.md`](CONTEXT.md) — agent/contributor navigation guide (read order, workspace shape)
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — canonical layout, install steps, validation commands
- [`SECURITY.md`](SECURITY.md) — vulnerability reporting, automation, incident response
- [`CHANGELOG.md`](CHANGELOG.md) — notable changes per release
- [`ONBOARDING.md`](ONBOARDING.md) — extended onboarding notes
- [`CLAUDE.md`](CLAUDE.md) — project instructions for AI coding assistants
- `docs/` — architecture deep-dives, dated reports, design docs

## Prerequisites

- Python 3.13+ (`.python-version`)
- Node.js 24+ (`.nvmrc`)
- Docker (for `docker-compose.yml`)
- `uv` for Python workspace management

## Root commands

```bash
python ops/scripts/run_workspace_smoke.py --scope all   # smoke across all projects
python ops/scripts/healthcheck.py                       # import + connectivity checks
npm run build:all
npm run test:all
npm run lint:all
npm run typecheck:all
docker compose config                                   # validate compose stack
```

## Per-project entry points

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and each project's own README:

- `apps/desci-platform/biolinker/README.md`
- `apps/AgriGuard/README.md`
- `automation/DailyNews/README.md`
- `automation/getdaytrends/README.md`

## Security

Vulnerabilities and supply-chain concerns are tracked per [`SECURITY.md`](SECURITY.md). The repo enforces SHA-pinned GitHub Actions via `pinact` and runs `zizmor`, CodeQL, Gitleaks, Bandit, and `pip-audit` on every PR.

## License

[MIT](LICENSE) © 2026 biojuho
