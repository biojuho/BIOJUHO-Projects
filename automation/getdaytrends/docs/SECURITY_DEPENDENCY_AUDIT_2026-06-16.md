# Dependency Security Audit — getdaytrends (2026-06-16)

Report-only. Version bumps are a user decision (workspace policy: no automatic
dependency updates). This audit maps `pip-audit` findings to getdaytrends'
**declared** dependencies so launch decisions are based on this product's real
attack surface, not the shared workspace `.venv`.

## Method

`uvx pip-audit` was run against a `pip freeze` of the shared workspace `.venv`
(308 PyPI packages). That environment contains dependencies from **all**
workspace projects (desci-platform, AgriGuard, DailyNews, …), so most findings
belong to other projects, not getdaytrends. Findings below are filtered against
`automation/getdaytrends/pyproject.toml`.

## getdaytrends-relevant findings

| Package | Installed | Advisory | Fix | Relevance |
| --- | --- | --- | --- | --- |
| python-dotenv | 1.2.1 | CVE-2026-28684 | 1.2.2 | **Direct dep.** LOW — local `.env` parsing, not a remote input path. Fix `1.2.2` is inside the existing `>=1.0.0,<2.0` constraint, so a `uv lock` refresh adopts it with no pyproject change. |

No other audited CVE maps to a getdaytrends declared dependency:

- **pytest 9.0.2 / CVE-2025-71176** — getdaytrends pins `pytest>=8.3,<8.4`; the
  9.0.2 in the shared venv belongs to another project. Dev-only regardless.
- **pyjwt, python-multipart, sqladmin, pypdf, pillow, tornado, pygments,
  pyasn1, uv** — none are getdaytrends dependencies. Code search confirms no
  `jwt`, `multipart`/`UploadFile`, or `sqladmin` usage in getdaytrends runtime.

## Cross-project note (for the workspace owner)

The shared venv flagged advisories that are genuinely relevant to **other**
projects' launches and worth triaging there (not in getdaytrends):

Mapped to the project that **directly declares** each package (grep over each
project's `pyproject.toml` / `requirements*.txt`):

| Package | Fix | Declared by | Severity |
| --- | --- | --- | --- |
| **pypdf** 6.6.2 | 6.12.0 | `apps/desci-platform/backend` | **16 CVEs — HIGH.** desci parses research/RFP PDFs (untrusted input), so PDF-parser CVEs are directly reachable. Triage first. |
| **pyjwt** 2.11.0 | 2.13.0 | `mcp/notebooklm-mcp` | 7 PYSEC — auth-critical wherever JWTs are verified. |
| **python-multipart** 0.0.22 | 0.0.27 | `apps/AgriGuard/backend`, `apps/desci-platform/backend`, `mcp/notebooklm-mcp` | 2 CVEs — form-parse DoS on the FastAPI apps. |
| **sqladmin** 0.23.0 | 0.25.1 | `apps/AgriGuard/backend` | admin-UI CVE — relevant if the admin surface is exposed. |
| **pygments** 2.19.2 | 2.20.0 | `mcp/notebooklm-mcp` | LOW. |
| **pillow**, **tornado** | — | (not directly declared) | transitive only; bump via whatever pulls them. |

These were not changed here: they live in other projects' dependency sets, and
those trees are currently mid-change in parallel sessions. The single highest
priority is **desci-platform pypdf** (untrusted-PDF parsing × 16 CVEs).

## Node side (`npm audit`, found via the CI "Node npm audit" gate)

The Python `uv`/`pip-audit` pass above misses the Node frontends. `npm audit`
per lockfile surfaced — this is what fails the "Dependency Audit (Node)" check
on the open dependabot PRs (#267/#268), repo-wide and unrelated to those Python
bumps. All are fixable in-range via `npm audit fix` in the named directory:

| Project | Package | Severity | Advisory |
| --- | --- | --- | --- |
| `apps/AgriGuard/frontend` | form-data | **HIGH** | GHSA-hmw2-7cc7-3qxx (CRLF injection via unescaped multipart field/file names) |
| `apps/desci-platform/frontend` | dompurify | moderate | GHSA-vxr8-fq34-vvx9 (Trusted Types policy survives clearConfig → XSS poisoning) |
| `apps/desci-platform/frontend` | protobufjs | moderate | GHSA-f38q-mgvj-vph7 (schema names can shadow runtime properties) |

`apps/dashboard`, both `contracts/`, and `mcp/canva-mcp` audited clean. The
root workspace lockfile is clean. getdaytrends has no Node runtime, so it is
unaffected. Highest Node priority: AgriGuard `form-data` (HIGH).

## Recommendation

- getdaytrends launch is **not blocked** by a dependency CVE. The single
  in-scope item (python-dotenv → 1.2.2) is low severity and in-range; adopt it
  on the next intentional `uv lock` refresh.
- Cross-project priority order (report-only; the owner decides bumps):
  desci-platform `pypdf`→6.12.0 (untrusted-PDF × 16 CVEs) first, then
  notebooklm-mcp `pyjwt`→2.13.0 (auth), then `python-multipart`→0.0.27 across
  the FastAPI apps, then AgriGuard `sqladmin`→0.25.1.
