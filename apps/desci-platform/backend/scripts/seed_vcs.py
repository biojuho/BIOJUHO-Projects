"""
Seed the ``vc_firms`` Postgres table from ``data/vcs_seed.json``.

Run from the backend directory:

    DATABASE_URL=postgres://... python scripts/seed_vcs.py
    DATABASE_URL=postgres://... python scripts/seed_vcs.py --dry-run
    DATABASE_URL=postgres://... python scripts/seed_vcs.py --truncate

The upsert is idempotent (``on conflict (id) do update``) so the script
can run safely in production deploys, in CI, and in local Postgres
profiles. ``--dry-run`` reports what would happen without writing.
``--truncate`` clears the table before seeding (useful when removing
firms from the JSON source).

Apply the schema first if it has not been applied:

    psql "$DATABASE_URL" \\
        -f apps/desci-platform/supabase/migrations/0001_core_schema.sql
    psql "$DATABASE_URL" \\
        -f apps/desci-platform/supabase/migrations/0002_vc_firms.sql
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

SEED_PATH = REPO_ROOT / "data" / "vcs_seed.json"


def _load_records() -> list[dict]:
    raw = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"{SEED_PATH} must contain a JSON array")
    return raw


async def _seed(database_url: str, *, dry_run: bool, truncate: bool) -> dict:
    import asyncpg

    records = _load_records()
    print(f"[seed_vcs] {len(records)} VC records in {SEED_PATH.name}")

    if dry_run:
        sample = ", ".join(r["id"] for r in records[:3])
        print(f"[seed_vcs] --dry-run: would upsert {len(records)} rows (first ids: {sample}…)")
        return {"dry_run": True, "rows": len(records)}

    conn = await asyncpg.connect(database_url, statement_cache_size=0)
    try:
        if truncate:
            print("[seed_vcs] truncating vc_firms (--truncate)")
            await conn.execute("truncate table vc_firms")

        sql = (
            "insert into vc_firms (id, name, country, website, investment_thesis, "
            "preferred_stages, portfolio_keywords, contact_email, updated_at) "
            "values ($1, $2, $3, $4, $5, $6, $7, $8, now()) "
            "on conflict (id) do update set "
            "name = excluded.name, "
            "country = excluded.country, "
            "website = excluded.website, "
            "investment_thesis = excluded.investment_thesis, "
            "preferred_stages = excluded.preferred_stages, "
            "portfolio_keywords = excluded.portfolio_keywords, "
            "contact_email = excluded.contact_email, "
            "updated_at = now()"
        )

        inserted = 0
        async with conn.transaction():
            for row in records:
                await conn.execute(
                    sql,
                    row["id"],
                    row["name"],
                    row.get("country", "KR"),
                    row.get("website"),
                    row["investment_thesis"],
                    list(row.get("preferred_stages") or []),
                    list(row.get("portfolio_keywords") or []),
                    row.get("contact_email"),
                )
                inserted += 1

        total = await conn.fetchval("select count(*) from vc_firms")
        print(f"[seed_vcs] upserted {inserted} rows; vc_firms now contains {total} rows")
        return {"upserted": inserted, "total_after": total}
    finally:
        await conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed vc_firms from JSON")
    parser.add_argument("--dry-run", action="store_true", help="Show actions without writing")
    parser.add_argument("--truncate", action="store_true", help="Clear table before seeding")
    args = parser.parse_args()

    database_url = os.getenv("DATABASE_URL", "").strip()
    if not args.dry_run and not database_url:
        print("[seed_vcs] DATABASE_URL is required (or use --dry-run)", file=sys.stderr)
        return 2

    try:
        result = asyncio.run(_seed(database_url, dry_run=args.dry_run, truncate=args.truncate))
    except Exception as exc:
        print(f"[seed_vcs] FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"[seed_vcs] OK: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
