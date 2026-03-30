# Security Policy

## Secret Management

### Rules
- **NEVER** commit `.env` files, API keys, tokens, or credentials
- All secrets are stored in `.env` files (gitignored) or environment variables
- `.gitignore` blocks: `.env`, `.env.*`, `credentials.json`, `token*.txt`, `serviceAccountKey.json`

### Tooling
- **Gitleaks**: Pre-commit hook scans for secrets before every commit
- **detect-private-key**: Pre-commit hook catches accidental private key commits
- **Gitleaks Action**: CI pipeline scans full git history on every PR

### If a Secret is Leaked
1. Rotate the compromised key immediately
2. Run `gitleaks detect --source . --verbose` to confirm scope
3. If committed to git history, use `git filter-repo` to purge (coordinate with team)
4. Update the key in all `.env` files and deployment environments

## Dependency Management

### Automated Scanning
- **Dependabot**: 11 ecosystem configs, weekly scans every Monday
  - Python (pip): root, DailyNews, GetDayTrends, AgriGuard, BioLinker
  - Node (npm): root, AgriGuard frontend, DeSci frontend/contracts, Dashboard, Canva MCP
  - GitHub Actions: monthly

### Vulnerability Patching SLA
| Severity | Patch Within | Action |
|----------|-------------|--------|
| Critical | 24 hours | Immediate hotfix PR |
| High | 7 days | Next sprint |
| Medium | 30 days | Backlog |
| Low | 90 days | Best effort |

### CI Pipeline
- **pip-audit**: Scans all `requirements.txt` files on every PR
- **npm audit**: Scans all `package.json` files on every PR

## Audit Logging

### What is Logged
Every HTTP request to FastAPI services records:
- `service`: Service name (agriguard, getdaytrends, dashboard, biolinker)
- `user_id`: From `X-User-ID` header or client IP
- `method`: HTTP method
- `path`: Request path
- `status`: Response status code
- `duration_ms`: Request duration
- `client_ip`: Client IP address

### Excluded Paths
`/metrics`, `/health`, `/docs`, `/openapi.json`, `/redoc` are excluded to reduce noise.

### Log Format
JSON structured logs via `structlog` (Loki-compatible). Falls back to stdlib logging.

### Log Retention
- Loki: 7 days (configurable in `ops/monitoring/loki.yml`)
- Grafana dashboards: "Error Logs" panel filters for error/exception/traceback

## Pre-Commit Hooks

Install and activate:
```bash
pip install pre-commit
pre-commit install
```

Active hooks:
1. **gitleaks** — Secret scanning
2. **detect-private-key** — Private key detection
3. **ruff** — Python linting + formatting
4. **check-yaml/json/toml** — Config file validation
5. **check-added-large-files** — Blocks files >1MB
6. **check-merge-conflict** — Catches unresolved conflicts

## API Security

### Rate Limiting
- BioLinker: `/analyze` 10/min, `/match/paper` 30/min
- All services: No public endpoints without rate limiting in production

### Authentication
- AgriGuard: JWT-based auth via `get_current_user` dependency
- BioLinker: Firebase Auth + tier-based access control
- DailyNews/GetDayTrends: Internal services, no public auth required

### CORS
- Development: `localhost:5173`, `localhost:5174`
- Production: Configured via `ALLOWED_ORIGINS` environment variable

## Monitoring & Alerting

### Prometheus Alert Rules
| Alert | Severity | Threshold |
|-------|----------|-----------|
| ServiceDown | Critical | Service unreachable for >2min |
| HighErrorRate | Warning | >5% 5xx rate over 5min |
| HighLatency | Warning | p95 >5s over 5min |
| PrometheusHighMemory | Warning | >1GB resident memory |

### AlertManager
- Critical alerts route to Telegram (when configured)
- All alerts visible at http://localhost:9093

## LLM Cost Controls

### Budget Auto-Downgrade
| Threshold | Action |
|-----------|--------|
| $1.50/day | HEAVY tier → MEDIUM |
| $1.80/day | MEDIUM tier → LIGHTWEIGHT |
| $2.00/day | Hard block (RATE_LIMIT.lock) |

All thresholds configurable via environment variables:
- `LLM_DAILY_BUDGET`, `LLM_BUDGET_DOWNGRADE_HEAVY`, `LLM_BUDGET_DOWNGRADE_MEDIUM`
