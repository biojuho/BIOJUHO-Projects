# AgriGuard Database Performance Benchmark

- Generated at: 2026-03-25T08:36:56.890463+00:00
- Rounds: 5
- SQLite DB: `D:\AI 프로젝트\AgriGuard\backend\agriguard.db`
- PostgreSQL: `postgresql://agriguard:***@localhost:5432/agriguard`

## Results

| Query | Category | SQLite (ms) | PostgreSQL (ms) | Speedup |
|-------|----------|-------------|-----------------|---------|
| COUNT all products | COUNT | 0.31 | 1.86 | [-] 0.2x |
| SELECT products with index | SELECT+INDEX | 0.48 | 1.73 | [-] 0.3x |
| JOIN products → tracking_events | JOIN+GROUP | 5.95 | 5.94 | [+] 1.0x |
| Recent tracking events | JOIN+ORDER | 4.43 | 5.23 | [-] 0.8x |
| User statistics | GROUP | 0.70 | 1.60 | [-] 0.4x |

## Notes

- Speedup > 1x means PostgreSQL is faster
- Results depend on data volume, indexing, and connection latency
- Current data volume: 15452 rows
