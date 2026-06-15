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

- **pyjwt 2.11.0** — 7 PYSEC advisories. Auth-critical wherever JWTs are
  verified (desci-platform / AgriGuard FastAPI backends). Highest priority.
- **python-multipart 0.0.22**, **sqladmin 0.23.0**, **tornado 6.5.4** — web
  surface (form parsing / admin UI / server) for the FastAPI apps.
- **pypdf 6.6.2** (16 CVEs), **pillow 12.1.0** — only relevant where untrusted
  PDFs/images are parsed.

These were not changed here: they live in other projects' dependency sets, and
those trees are currently mid-change in parallel sessions.

## Recommendation

- getdaytrends launch is **not blocked** by a dependency CVE. The single
  in-scope item (python-dotenv → 1.2.2) is low severity and in-range; adopt it
  on the next intentional `uv lock` refresh.
- Triage the pyjwt/web findings inside desci-platform / AgriGuard separately.
