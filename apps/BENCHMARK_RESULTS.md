# AgriGuard Database Performance Benchmark

- Generated at: 2026-04-02T04:53:19.092363+00:00
- Rounds: 5
- SQLite DB: `D:\AI project\apps\AgriGuard\backend\agriguard.db`
- PostgreSQL: `postgresql://agriguard:***@localhost:5432/agriguard`

## Results

| Query | Category | SQLite (ms) | PostgreSQL (ms) | Speedup |
|-------|----------|-------------|-----------------|---------|
| COUNT all products | COUNT | 0.29 | 1.54 | [-] 0.2x |
| SELECT products with index | SELECT+INDEX | 0.62 | 1.68 | [-] 0.4x |
| JOIN products → tracking_events | JOIN+GROUP | 5.40 | 5.36 | [+] 1.0x |
| Recent tracking events | JOIN+ORDER | 3.69 | 5.44 | [-] 0.7x |
| User statistics | GROUP | 0.68 | 1.65 | [-] 0.4x |

## Notes

- Speedup > 1x means PostgreSQL is faster
- Results depend on data volume, indexing, and connection latency
- Current data volume: 17185 rows
